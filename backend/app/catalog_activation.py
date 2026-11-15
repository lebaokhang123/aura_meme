"""Explicit reviewed catalog activation on guarded local demo/test/E2E; never grants inventory."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5, uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, undefer

from app.catalog import read_manifest
from app.catalog_audit import bounded_bytes
from app.catalog_rights import SHA256, reviewed_source_rights
from app.aura_lock import lock_aura_mutation
from app.config import CatalogSettings, load_settings
from app.db import create_db_engine
from app.models import AdminAuditLog, AssetItem, CaseDefinition, CaseLootRarity, CaseLootTable, CasePoolItem, RewardPolicyVersion, Role, User, UserRole
from app.vault_v1_policy import EFFECT_KEYS, WEIGHTS


def validate_target(raw, *, allow_demo=False):
    try:
        target = make_url(raw)
        roles = {'aurameme_test':'aurameme_test','aurameme_e2e':'aurameme_e2e_app'}
        if allow_demo:
            roles['aurameme_demo'] = 'aurameme_demo'
        ports = {5432,55434,55435} if target.database == 'aurameme_e2e' else {5432}
        if (target.drivername != 'postgresql+psycopg' or target.host not in {'localhost','127.0.0.1','::1'}
                or target.database not in roles or target.username != roles[target.database]
                or (target.port or 5432) not in ports or target.query or not target.password):
            raise ValueError
    except Exception:
        raise ValueError('Activation requires an explicit dedicated loopback demo/test/E2E database and matching role.') from None
    return target.database


def activation_guard(db, actor_id):
    from app.demo import demo_connection, reviewed_demo_schema
    database = validate_target(db.connection().engine.url.render_as_string(hide_password=False), allow_demo=True)
    role = {'aurameme_test':'aurameme_test','aurameme_e2e':'aurameme_e2e_app','aurameme_demo':'aurameme_demo'}[database]
    if tuple(db.execute(text('SELECT current_database(),current_user,current_schema()')).one()) != (database,role,'public'):
        raise ValueError('Unsafe catalog database identity.')
    if database == 'aurameme_demo':
        demo_connection(db.connection())
    reviewed_demo_schema(db.connection())
    if db.scalar(text('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user')):
        raise ValueError('Catalog activation forbids privileged application roles.')
    lock_aura_mutation(db)
    actor = db.scalar(select(User).join(UserRole,UserRole.user_id==User.id).join(Role,Role.id==UserRole.role_id).where(
        User.id==actor_id,User.status=='active',Role.code=='ADMIN').with_for_update(of=User,read=True))
    if actor is None:
        raise ValueError('An existing active database ADMIN is required.')
    # Readers lock the legacy common case, then runtime cases, before pools and assets.
    list(db.scalars(select(CaseDefinition.id).order_by(CaseDefinition.slug != 'common',
        CaseDefinition.runtime_kind,CaseDefinition.id).with_for_update()))


def audit_catalog(db, actor_id, action, digest, now, details):
    db.add(AdminAuditLog(id=uuid4(),actor_id=actor_id,action=action,target_type='catalog_manifest',target_id=digest,
        before_json=None,after_json=details,created_at=now))
    db.flush()


def approved_manifest(manifest, actual_digest, approved_digest):
    if (not isinstance(approved_digest,str) or not SHA256.fullmatch(approved_digest) or actual_digest != approved_digest):
        raise ValueError('Explicit Owner approval must match the exact canonical manifest SHA256.')
    if not manifest.items:
        raise ValueError('A nonempty reviewed catalog is required.')
    for field in ('id','slug','sha256'):
        if len({getattr(item,field) for item in manifest.items}) != len(manifest.items):
            raise ValueError('Duplicate catalog identity or bytes.')
    required = {(kind, rarity) for kind in {item.kind for item in manifest.items} for rarity in 'DCBAS'}
    available = set()
    for item in manifest.items:
        if (item.kind not in {'avatar','background'} or item.source_rights.review_status != 'approved'
                or item.name_review_status != 'approved' or not item.name_vi
                or not reviewed_source_rights(item.source_rights.model_dump() | {'sha256':item.sha256})):
            raise ValueError('Every item needs explicit rights and name approval.')
        if item.kind == 'background' and item.effect_key != EFFECT_KEYS['DCBAS'.index(item.rarity)]:
            raise ValueError('Background renderer must match its approved rarity.')
        available.add((item.kind,item.rarity))
    if available != required:
        raise ValueError('Complete five-rarity approved catalogs are required for each requested case.')
    return manifest


def activate_catalog(db, manifest, manifest_digest, approved_digest, now, *, actor_id):
    approved_manifest(manifest, manifest_digest, approved_digest)
    activation_guard(db,actor_id)
    db.execute(text('LOCK TABLE asset_items IN SHARE ROW EXCLUSIVE MODE'))
    for item in manifest.items:
        key = 'catalog/'+item.sha256+{'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[item.mime]
        asset = db.scalar(select(AssetItem).where(or_(AssetItem.id == item.id, AssetItem.slug == item.slug))
            .options(undefer(AssetItem.display_name),undefer(AssetItem.effect_key)).with_for_update())
        if asset is not None and ((asset.id,asset.slug,asset.kind,asset.collection,asset.rarity,asset.media_key) !=
                (item.id,item.slug,item.kind,item.collection,item.rarity,key)):
            raise ValueError('Conflicting identity; never overwrite catalog assets.')
        if db.scalar(select(AssetItem.id).where(AssetItem.source_rights['sha256'].astext == item.sha256,
                                              AssetItem.id != item.id)) is not None:
            raise ValueError('Duplicate catalog bytes across identities.')
        if asset is None:
            asset = AssetItem(id=item.id,slug=item.slug,kind=item.kind,collection=item.collection,
                rarity=item.rarity,media_key=key,active=False,created_at=now,updated_at=now)
            db.add(asset)
        asset.display_name,asset.effect_key = item.name_vi,item.effect_key
        asset.source_rights = item.source_rights.model_dump() | {
            'sha256':item.sha256,'mime':item.mime,'name_review_status':item.name_review_status,
            'manifest_sha256':manifest_digest,'catalog_version':manifest.version}
        asset.active,asset.updated_at = True,now
    db.flush()
    audit_catalog(db,actor_id,'catalog.activate',manifest_digest,now,{'asset_count':len(manifest.items),'kinds':sorted({item.kind for item in manifest.items})})



def publish_cases(db, manifest, manifest_digest, approved_digest, policy_owner, now):
    """Explicit isolated publication; caller owns one transaction with catalog activation."""
    approved_manifest(manifest,manifest_digest,approved_digest)
    activation_guard(db,policy_owner)
    db.execute(text('LOCK TABLE case_definitions, reward_policy_versions IN SHARE ROW EXCLUSIVE MODE'))
    policy_id=uuid5(NAMESPACE_URL,'aurameme:vault:v1:policy:'+manifest_digest)
    config={'type':'free-vault-v1','catalog_manifest_sha256':manifest_digest}
    policy=db.get(RewardPolicyVersion,policy_id)
    if policy is None:
        version=db.scalar(select(func.coalesce(func.max(RewardPolicyVersion.version),0)))+1
        policy=RewardPolicyVersion(id=policy_id,version=version,config_json=config,status='draft',
                                  effective_at=now,created_by=policy_owner,created_at=now)
        db.add(policy);db.flush()
    elif (policy.config_json!=config or policy.status!='published' or policy.effective_at>now
          or policy.created_by!=policy_owner):
        raise ValueError('Conflicting immutable publication policy.')
    results={}
    for kind,label in (('avatar','Rương Meme'),('background','Rương Background')):
        if not any(item.kind==kind for item in manifest.items):
            continue
        case_id=uuid5(NAMESPACE_URL,'aurameme:vault:v1:case:'+kind)
        pool_id=uuid5(NAMESPACE_URL,'aurameme:vault:v1:pool:'+kind+':'+manifest_digest)
        slug='free-meme-v1' if kind=='avatar' else 'free-background-v1'
        case=db.scalar(select(CaseDefinition).where(or_(CaseDefinition.id==case_id,
            CaseDefinition.runtime_kind==kind,CaseDefinition.slug==slug)).options(undefer(CaseDefinition.runtime_kind)).with_for_update())
        if case is None:
            case=CaseDefinition(id=case_id,slug=slug,label=label,cost_khi_van=0,status='draft',
                                runtime_kind=kind,created_at=now,updated_at=now)
            db.add(case);db.flush()
        elif ((case.id,case.slug,case.runtime_kind,case.cost_khi_van)!=(case_id,slug,kind,0)
              or case.status not in {'draft','active'}):
            raise ValueError('Conflicting runtime case identity; never overwrite.')
        expected={(item.id,item.rarity,1) for item in manifest.items if item.kind==kind}
        for item in (item for item in manifest.items if item.kind==kind):
            asset=db.scalar(select(AssetItem).where(AssetItem.id==item.id).options(
                undefer(AssetItem.display_name),undefer(AssetItem.effect_key)).with_for_update(read=True))
            from app.vault_runtime import ready_runtime_asset
            if (not ready_runtime_asset(asset,kind) or asset.rarity!=item.rarity
                    or asset.source_rights.get('manifest_sha256')!=manifest_digest):
                raise ValueError('Approved activated catalog must exactly match publication manifest.')
        pool=db.get(CaseLootTable,pool_id)
        latest=db.scalar(select(func.coalesce(func.max(CaseLootTable.odds_version),0)).where(CaseLootTable.case_id==case_id))
        if pool is not None:
            saved_weights=dict(db.execute(select(CaseLootRarity.rarity,CaseLootRarity.weight_bps).where(CaseLootRarity.loot_table_id==pool_id)).all())
            saved_items=set(db.execute(select(CasePoolItem.asset_id,CasePoolItem.rarity,CasePoolItem.item_weight).where(CasePoolItem.loot_table_id==pool_id)).all())
            if ((pool.case_id,pool.policy_id,pool.band_no,pool.min_earned_xp,pool.max_earned_xp,pool.status)
                    !=(case_id,policy_id,1,0,None,'published') or pool.active_from>now or pool.odds_version!=latest
                    or saved_weights!=dict(zip('DCBAS',WEIGHTS)) or saved_items!=expected):
                raise ValueError('Conflicting or superseded immutable pool; never rewrite.')
        else:
            pool=CaseLootTable(id=pool_id,case_id=case_id,odds_version=latest+1,band_no=1,min_earned_xp=0,
                max_earned_xp=None,policy_id=policy_id,status='draft',active_from=now,created_at=now)
            db.add(pool);db.flush()
            for rarity,weight in zip('DCBAS',WEIGHTS):
                db.add(CaseLootRarity(loot_table_id=pool_id,rarity=rarity,weight_bps=weight))
            db.flush()
            for asset_id,rarity,weight in sorted(expected,key=lambda row:str(row[0])):
                db.add(CasePoolItem(loot_table_id=pool_id,asset_id=asset_id,rarity=rarity,item_weight=weight))
            db.flush();pool.status='published';db.flush()
        if case.status!='active':
            case.status='active';case.updated_at=now
        results[kind]=case_id
    if policy.status=='draft':
        policy.status='published'
    db.flush()
    # Validate the exact read/open policy before this publication transaction can commit.
    from app.vault_runtime import load_runtime_pool
    for case_id in results.values():
        case=db.scalar(select(CaseDefinition).where(CaseDefinition.id==case_id).options(undefer(CaseDefinition.runtime_kind)))
        load_runtime_pool(db,case,now)
    audit_catalog(db,policy_owner,'vault.cases.publish',manifest_digest,now,{'case_ids':{kind:str(identity) for kind,identity in results.items()}})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--approved-manifest-sha256',required=True)
    parser.add_argument('--activate-isolated-catalog',action='store_true',required=True)
    parser.add_argument('--publish-isolated-v1-cases',action='store_true')
    parser.add_argument('--policy-owner',type=UUID,required=True)
    parser.add_argument('--demo-root',type=Path,help='Explicit validated demo.local config root; never falls back to development.')
    args = parser.parse_args(argv)
    try:
        # Validation and approval happen before reading DB configuration or constructing any engine.
        manifest = read_manifest(args.manifest)
        digest = sha256(bounded_bytes(args.manifest)).hexdigest()
        approved_manifest(manifest,digest,args.approved_manifest_sha256)
        if args.demo_root is not None:
            from app.demo import demo_environment,activate_demo
            demo_environment(args.demo_root)
            activate_demo(args.demo_root)
        settings = load_settings()
        target = validate_target(settings.database_url.get_secret_value(),allow_demo=args.demo_root is not None)
        engine = create_db_engine(settings)
        try:
            with Session(engine) as db,db.begin():
                now=datetime.now(timezone.utc)
                activation_guard(db,args.policy_owner)
                # Copy approved bytes only; original source package remains unchanged.
                root = CatalogSettings().catalog_storage_root
                if any(path.is_symlink() or path.is_junction() for path in (root,*root.parents)):
                    raise ValueError('Catalog storage links are forbidden.')
                root.mkdir(parents=True,exist_ok=True)
                for item in manifest.items:
                    suffix={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[item.mime]
                    destination=root/(item.sha256+suffix)
                    data=bounded_bytes(args.manifest.parent/item.file)
                    if sha256(data).hexdigest() != item.sha256:
                        raise ValueError('Approved package bytes changed.')
                    if destination.exists():
                        if destination.is_symlink() or destination.stat().st_nlink != 1 or destination.read_bytes() != data:
                            raise ValueError('Conflicting catalog storage; never overwrite.')
                    else:
                        with destination.open('xb') as stream: stream.write(data)
                activate_catalog(db,manifest,digest,args.approved_manifest_sha256,now,actor_id=args.policy_owner)
                if args.publish_isolated_v1_cases:
                    publish_cases(db,manifest,digest,args.approved_manifest_sha256,args.policy_owner,now)
        finally:
            engine.dispose()
        print(f'Approved catalog activated on guarded local {target}; cases published: {args.publish_isolated_v1_cases}; no user grants.')
    except Exception:
        parser.exit(1,'Catalog activation refused or rolled back; inspect the reviewed manifest, operator and local configuration.\n')


if __name__ == '__main__':
    main()
