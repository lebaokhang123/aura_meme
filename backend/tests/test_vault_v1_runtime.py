from vault_test_rights import synthetic_rights
"""Free Vault HTTP behavior against isolated rollback-only synthetic fixtures."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID,uuid4
import json

import pytest
from sqlalchemy import event,text

from test_auth import auth,migrated,register,login,csrf,ORIGIN
from app.vault_v1_policy import EFFECT_KEYS,WEIGHTS


def seed_runtime(c,owner,now,before_publish=None):
    policy=uuid4();cases={};assets={};pools=[]
    c.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,:config,'draft',:now,:owner,:now)"),
              {'id':policy,'config':json.dumps({'type':'free-vault-v1'}),'now':now,'owner':owner})
    for kind in ('avatar','background'):
        case,pool=uuid4(),uuid4();cases[kind]=case;pools.append(pool);assets[kind]=[]
        c.execute(text("INSERT INTO case_definitions (id,slug,label,cost_khi_van,status,created_at,updated_at,runtime_kind) VALUES (:id,:slug,:kind,0,'draft',:now,:now,:kind)"),
                  {'id':case,'slug':'free-'+kind,'kind':kind,'now':now})
        c.execute(text("INSERT INTO case_loot_tables VALUES (:id,:case,1,1,0,NULL,:policy,'draft',:now,:now)"),
                  {'id':pool,'case':case,'policy':policy,'now':now})
        for index,(rarity,weight) in enumerate(zip('DCBAS',WEIGHTS)):
            asset=uuid4();assets[kind].append(asset);digest=asset.hex*2
            rights=synthetic_rights(digest,name_review_status='approved')
            c.execute(text("INSERT INTO asset_items (id,slug,kind,collection,rarity,media_key,source_rights,active,created_at,updated_at,display_name,effect_key) VALUES (:id,:slug,:kind,'synthetic',:rarity,:key,CAST(:rights AS jsonb),true,:now,:now,:name,:effect)"),
                      {'id':asset,'slug':'fixture-'+asset.hex,'kind':kind,'rarity':rarity,'key':'catalog/'+digest+'.png',
                       'rights':json.dumps(rights),'now':now,'name':kind+' '+rarity,'effect':EFFECT_KEYS[index] if kind=='background' else None})
            c.execute(text('INSERT INTO case_loot_rarities VALUES (:pool,:rarity,:weight)'),{'pool':pool,'rarity':rarity,'weight':weight})
            c.execute(text('INSERT INTO case_pool_items VALUES (:pool,:asset,:rarity,1)'),{'pool':pool,'asset':asset,'rarity':rarity})
        if before_publish is not None:
            before_publish(c,kind,case,pool,assets[kind])
        c.execute(text("UPDATE case_loot_tables SET status='published' WHERE id=:id"),{'id':pool})
        c.execute(text("UPDATE case_definitions SET status='active' WHERE id=:id"),{'id':case})
    c.execute(text("UPDATE reward_policy_versions SET status='published' WHERE id=:id"),{'id':policy})
    return cases,policy,pools,assets


@pytest.fixture
def runtime_vault(auth,monkeypatch):
    client,c=auth;owner=UUID(register(client).json()['id']);assert login(client).status_code==200
    monkeypatch.setattr(client.app.state,'vault',SimpleNamespace(vault_runtime_enabled=True),raising=False)
    cases,policy,pools,assets=seed_runtime(c,owner,client.app.state.auth.now())
    import app.vault_runtime as runtime
    from app.vault import draw
    monkeypatch.setattr(runtime,'draw',lambda pool,randbelow:draw(pool,randbelow=lambda n:0))
    return client,c,owner,cases,policy,pools,assets


def opening(client,case,key='fixture-runtime-request-1'):
    if not hasattr(client, '_vault_token'):
        client._vault_token = csrf(client)
    return client.post('/api/v1/vault/cases/'+str(case)+'/open',headers={
        'Origin':ORIGIN,'X-CSRF-Token':client._vault_token,'Idempotency-Key':key})


def counts(c):
    return {name:c.scalar(text('SELECT count(*) FROM '+name)) for name in
            ('case_opens','inventory_grants','user_inventory','wallets','wallet_transactions','user_progress','aura_ledger')}


@pytest.mark.integration
def test_free_open_receipt_retry_conflict_and_owned_catalog(runtime_vault):
    client,c,owner,cases,_,_,assets=runtime_vault
    catalog=client.get('/api/v1/catalog?kind=avatar&q=avatar').json()
    assert catalog['pagination']['total']==5 and not any(row['owned'] for row in catalog['items'])
    response=opening(client,cases['avatar']);assert response.status_code==200,response.text
    first=response.json();assert first['reward']['id']==str(assets['avatar'][0]) and not first['already_processed']
    assert first['cost_khi_van']==first['khi_van_balance']==0
    assert counts(c)=={'case_opens':1,'inventory_grants':1,'user_inventory':1,'wallets':0,'wallet_transactions':0,'user_progress':1,'aura_ledger':1}
    retry=opening(client,cases['avatar']);assert retry.status_code==200
    assert retry.json() | {'already_processed':False} == first
    conflict=opening(client,cases['background']);assert conflict.status_code==409 and conflict.json()['error']['code']=='IDEMPOTENCY_CONFLICT'
    assert client.get('/api/v1/vault/opens/by-request?key=fixture-runtime-request-1').json()['open_id']==first['open_id']
    items=client.get('/api/v1/catalog?kind=avatar').json()['items']
    assert sum(row['owned'] for row in items)==1
    inventory=client.get('/api/v1/inventory/me').json()['items'];assert len(inventory)==1 and inventory[0]['quantity']==1


@pytest.mark.integration
def test_cooldown_boundaries_repeat_every_ten_and_share_case_kinds(runtime_vault):
    client,c,_,cases,_,_,_=runtime_vault
    current=client.app.state.auth.now()
    for number in range(1,22):
        client.app.state.auth.now=lambda:current
        response=opening(client,cases['avatar' if number%2 else 'background'],f'fixture-runtime-{number:03}')
        assert response.status_code==200,response.text
        wait=5 if number%10==0 else 2
        due=response.json()['next_open_at']
        from datetime import datetime
        assert datetime.fromisoformat(due)==current+timedelta(seconds=wait)
        client.app.state.auth.now=lambda:current+timedelta(seconds=wait,microseconds=-1)
        blocked=opening(client,cases['background'],f'fixture-blocked-{number:03}')
        assert blocked.status_code==429 and blocked.headers['Retry-After']=='1',blocked.text
        assert blocked.json()['error']['details']['next_open_at']==due
        assert opening(client,cases['avatar' if number%2 else 'background'],f'fixture-runtime-{number:03}').json()['already_processed']
        current+=timedelta(seconds=wait)
    assert counts(c)['case_opens']==21
    assert c.scalar(text('SELECT sum(quantity) FROM user_inventory'))==21


@pytest.mark.integration
def test_receipt_recovers_when_issuance_off_and_reward_rights_revoked(runtime_vault):
    client,c,_,cases,_,_,assets=runtime_vault
    first=opening(client,cases['avatar']);assert first.status_code==200
    c.execute(text('UPDATE asset_items SET active=false WHERE id=:id'),{'id':assets['avatar'][0]})
    client.app.state.vault.vault_runtime_enabled=False
    replay=opening(client,cases['avatar']);assert replay.status_code==200,replay.text
    reward=replay.json()['reward'];assert reward['available'] is False and reward['media_url'] is None
    assert client.get('/api/v1/vault/opens/by-request?key=fixture-runtime-request-1').json()['reward']==reward
    assert opening(client,cases['avatar'],'fixture-fresh-disabled').status_code==503
    assert counts(c)['case_opens']==1


@pytest.mark.integration
def test_avatar_background_equip_reset_and_real_wallet_balance(runtime_vault):
    from test_blog import mutation
    client,c,owner,cases,_,_,assets=runtime_vault
    c.execute(text('INSERT INTO wallets VALUES (:id,123,:now)'),{'id':owner,'now':client.app.state.auth.now()})
    first=opening(client,cases['avatar']);assert first.status_code==200 and first.json()['khi_van_balance']==123
    assert mutation(client,'PUT','/inventory/equipment/avatar',{'asset_id':str(assets['avatar'][0])}).status_code==200
    assert client.get('/api/v1/users/me').json()['avatar_url'].endswith(str(assets['avatar'][0]))
    now=client.app.state.auth.now()+timedelta(seconds=2);client.app.state.auth.now=lambda:now
    second=opening(client,cases['background'],'fixture-background-001');assert second.status_code==200,second.text
    assert mutation(client,'PUT','/inventory/equipment/background',{'asset_id':str(assets['background'][0])}).status_code==200
    assert len(client.get('/api/v1/inventory/equipment').json()['items'])==2
    assert mutation(client,'PUT','/inventory/equipment/background',{'asset_id':None}).status_code==200
    assert [row['slot_kind'] for row in client.get('/api/v1/inventory/equipment').json()['items']]==['avatar']
    assert c.scalar(text('SELECT khi_van_balance FROM wallets WHERE user_id=:id'),{'id':owner})==123
    assert counts(c)['wallet_transactions']==0


@pytest.mark.integration
@pytest.mark.parametrize('table',['case_opens','inventory_grants','user_inventory'])
def test_failed_insert_rolls_back_all_reward_state(runtime_vault,table):
    client,c,_,cases,_,_,_=runtime_vault
    def reject(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO '+table):raise RuntimeError('synthetic insertion failure')
    event.listen(c,'before_cursor_execute',reject)
    try:
        with pytest.raises(RuntimeError,match='synthetic insertion'):
            opening(client,cases['avatar'])
    finally:event.remove(c,'before_cursor_execute',reject)
    assert counts(c)['case_opens']==counts(c)['inventory_grants']==counts(c)['user_inventory']==0
    assert opening(client,cases['avatar']).status_code==200


@pytest.mark.integration
@pytest.mark.parametrize('invalid',['wrong-odds','unequal-items','missing-rarity','mixed-kind','pending-name','unready-asset','xp-band','quota-policy'])
def test_incomplete_runtime_case_never_publishes_or_grants(auth,monkeypatch,invalid):
    client,c=auth;owner=UUID(register(client).json()['id']);assert login(client).status_code==200
    monkeypatch.setattr(client.app.state,'vault',SimpleNamespace(vault_runtime_enabled=True),raising=False)
    def change(c,kind,case,pool,assets):
        if kind!='avatar':return
        if invalid=='wrong-odds':
            c.execute(text("UPDATE case_loot_rarities SET weight_bps=CASE WHEN rarity='D' THEN 6889 WHEN rarity='C' THEN 2001 ELSE weight_bps END WHERE loot_table_id=:pool"),{'pool':pool})
        elif invalid=='unequal-items':
            c.execute(text('UPDATE case_pool_items SET item_weight=2 WHERE loot_table_id=:pool'),{'pool':pool})
        elif invalid=='missing-rarity':
            c.execute(text("DELETE FROM case_pool_items WHERE loot_table_id=:pool AND rarity='S'"),{'pool':pool})
        elif invalid=='mixed-kind':
            c.execute(text("UPDATE asset_items SET kind='icon' WHERE id=:id"),{'id':assets[0]})
        elif invalid=='pending-name':
            c.execute(text("UPDATE asset_items SET source_rights=jsonb_set(source_rights,'{name_review_status}','\"pending\"') WHERE id=:id"),{'id':assets[0]})
        elif invalid=='unready-asset':
            c.execute(text('UPDATE asset_items SET active=false WHERE id=:id'),{'id':assets[0]})
        elif invalid=='xp-band':
            policy=c.scalar(text('SELECT policy_id FROM case_loot_tables WHERE id=:id'),{'id':pool})
            c.execute(text("INSERT INTO case_loot_tables VALUES (:id,:case,1,2,1,NULL,:policy,'draft',:now,:now)"),{'id':uuid4(),'case':case,'policy':policy,'now':client.app.state.auth.now()})
        else:
            policy=c.scalar(text('SELECT policy_id FROM case_loot_tables WHERE id=:id'),{'id':pool})
            c.execute(text("UPDATE reward_policy_versions SET config_json=CAST(:config AS jsonb) WHERE id=:id"),{'id':policy,'config':json.dumps({'type':'free-vault-v1','max_daily_opens':100})})
    cases,_,_,_=seed_runtime(c,owner,client.app.state.auth.now(),change)
    listing=client.get('/api/v1/vault/cases');assert listing.status_code==200,listing.text
    assert all(row['runtime_kind']!='avatar' for row in listing.json()['items'])
    response=opening(client,cases['avatar']);assert response.status_code==503,response.text
    assert counts(c)['case_opens']==counts(c)['inventory_grants']==counts(c)['user_inventory']==0


@pytest.mark.integration
def test_catalog_search_pagination_and_second_owner_are_global_but_isolated(runtime_vault):
    client,c,_,cases,_,_,_=runtime_vault
    assert client.get('/api/v1/catalog?q=%25').json()['pagination']['total']==0
    first=client.get('/api/v1/catalog?kind=avatar&page=1&page_size=2').json()
    last=client.get('/api/v1/catalog?kind=avatar&page=3&page_size=2').json()
    assert first['pagination']['total']==5 and len(first['items'])==2 and len(last['items'])==1
    assert opening(client,cases['avatar']).status_code==200
    client.cookies.clear()
    assert client.get('/api/v1/catalog').status_code==401
    assert client.get('/api/v1/vault/cases').json()['items']==[]
    assert register(client,username='second_owner',email='second-owner@example.com').status_code==201
    assert login(client,email='second-owner@example.com').status_code==200
    assert not any(row['owned'] for row in client.get('/api/v1/catalog').json()['items'])
    assert client.get('/api/v1/inventory/me').json()['items']==[]
    assert client.get('/api/v1/vault/opens/by-request?key=fixture-runtime-request-1').status_code==404

@pytest.mark.integration
def test_inventory_kind_filter_paginates_owned_items_and_keeps_quantities(runtime_vault):
    client,c,_,cases,_,_,_=runtime_vault
    start=client.app.state.auth.now()
    for index,kind in enumerate(('avatar','avatar','background')):
        now=start+timedelta(seconds=index*2);client.app.state.auth.now=lambda:now
        response=opening(client,cases[kind],f'fixture-kind-filter-{index}')
        assert response.status_code==200,response.text
    avatars=client.get('/api/v1/inventory/me?kind=avatar&page_size=1').json()
    backgrounds=client.get('/api/v1/inventory/me?kind=background&page_size=1').json()
    assert avatars['pagination']['total']==1 and avatars['items'][0]['quantity']==2
    assert all(row['asset']['kind']=='avatar' for row in avatars['items'])
    assert backgrounds['pagination']['total']==1 and backgrounds['items'][0]['quantity']==1
    assert all(row['asset']['kind']=='background' for row in backgrounds['items'])
    all_items=client.get('/api/v1/inventory/me').json()
    assert all_items['pagination']['total']==2 and sum(row['quantity'] for row in all_items['items'])==3
    assert client.get('/api/v1/inventory/me?kind=frame').json()['pagination']['total']==0
    assert client.get('/api/v1/inventory/me?kind=sound').status_code==422
