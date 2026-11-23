"""Provisioning plan is read-only; real API/role tests use isolated rollback fixtures."""
from uuid import UUID
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app import demo_accounts as setup
from app.demo import bootstrap_admin
from app.models import User,Profile,Role,UserRole,AdminAuditLog,AuthSession
from test_auth import auth,migrated,ORIGIN

def existing_accounts():
    ids = (setup.KHANG_DEV_ID, setup.KIEN_DEV_ID, UUID(int=3))
    return [{**row, "id": ident, "status": "active"} for row, ident in zip(setup.ACCOUNTS, ids)]

def test_empty_plan_refuses_to_create_protected_accounts():
    plan=setup.account_plan([],0)
    assert plan["conflicts"] and "approved IDs" in plan["conflicts"][0]
    with pytest.raises(ValueError):
        setup.apply_accounts(None, plan, {}, None)
    assert [row["username"] for row in plan["accounts"]]==["khang_dev","kien_dev","gigachad"]

def test_existing_complete_plan_is_idempotent_and_preserves_ids():
    rows=existing_accounts();plan=setup.account_plan(rows,2)
    assert not plan["writes"] and not plan["conflicts"]
    assert [r["id"] for r in plan["accounts"]]==[str(r["id"]) for r in rows]
    class RefuseClient:
        def __getattr__(self,key):pytest.fail("No API calls allowed for complete plan")
    assert setup.apply_accounts(RefuseClient(),plan,{},lambda ident:pytest.fail("No bootstrap"))=={r["username"]:str(r["id"]) for r in rows}

@pytest.mark.parametrize("change",[
    {"status":"locked"},{"display_name":"Someone else"},{"roles":["ADMIN"]},
    {"username":"another_owner"},{"email":"different@example.com"},
])
def test_existing_identity_conflicts_refuse_writes(change):
    rows=existing_accounts();rows[0]={**rows[0],**change}
    plan=setup.account_plan(rows,2);assert plan["conflicts"]
    with pytest.raises(ValueError):setup.apply_accounts(None,plan,{},None)

def test_never_bootstrap_over_an_existing_admin_or_remove_gigachad_roles():
    assert setup.account_plan([],1)["conflicts"]
    rows=existing_accounts();rows[2]["roles"]=["USER","ADMIN"]
    assert setup.account_plan(rows,2)["conflicts"]

@pytest.mark.parametrize("apply,confirmation,inputs,expected",[
    (False,"",[],0),
    (True,"cancel",[],1),
    (True,setup.CONFIRMATION,["Synthetic-password!","different-synthetic-password!"],1),
])
def test_cli_read_only_cancel_and_mismatch_never_write(monkeypatch,capsys,apply,confirmation,inputs,expected):
    from unittest.mock import Mock
    engine=Mock();values=iter(inputs)
    monkeypatch.setattr(setup,"demo_environment",lambda root:{"DATABASE_URL":"postgresql+psycopg://aurameme_demo:synthetic@127.0.0.1:5432/aurameme_demo"})
    monkeypatch.setattr(setup,"create_db_engine",lambda url:engine)
    monkeypatch.setattr(setup,"read_plan",lambda engine:setup.account_plan(existing_accounts()[:2],2))
    monkeypatch.setattr(setup,"activate_demo",lambda root:pytest.fail("Must not activate/write"))
    assert setup.main(["--apply"] if apply else [],ask=lambda prompt:confirmation,password=lambda prompt:next(values))==expected
    engine.dispose.assert_called_once()
    output=capsys.readouterr().out
    assert "Synthetic-password!" not in output and "different-synthetic-password!" not in output

@pytest.mark.integration
def test_real_bootstrap_audited_second_admin_and_idempotency(auth):
    client,connection=auth
    passwords={r["username"]:"Synthetic-"+r["username"]+"-password!" for r in setup.ACCOUNTS}
    def bootstrap(ident):
        with Session(bind=connection,join_transaction_mode="create_savepoint") as db,db.begin():
            bootstrap_admin(db,UUID(ident),lambda prompt:setup.CONFIRMATION)
    now = client.app.state.auth.now()
    role_id = UUID(int=42)
    connection.execute(Role.__table__.insert().values(id=role_id, code="USER", description="Fixture user"))
    records = [row | {"roles": ["USER"]} for row in existing_accounts()[:2]]
    for row in records:
        connection.execute(User.__table__.insert().values(
            id=row["id"], username=row["username"], email=row["email"], status="active",
            password_hash=client.app.state.auth.hasher.hash(passwords[row["username"]]),
            created_at=now, updated_at=now))
        connection.execute(Profile.__table__.insert().values(
            user_id=row["id"], display_name=row["display_name"], updated_at=now))
        connection.execute(UserRole.__table__.insert().values(user_id=row["id"], role_id=role_id, granted_at=now))
    ids=setup.apply_accounts(client,setup.account_plan(records,0),passwords,bootstrap,origin=ORIGIN)
    assert connection.scalar(select(func.count()).select_from(User))==3
    audits=connection.execute(select(AdminAuditLog.action,AdminAuditLog.actor_id,AdminAuditLog.target_id)).all()
    assert {a.action for a in audits}=={"demo.bootstrap_admin","user.roles"}
    assert all(str(a.actor_id)==ids["khang_dev"] for a in audits)
    assert any(a.action=="user.roles" and a.target_id==ids["kien_dev"] for a in audits)
    for account in setup.ACCOUNTS:
        name=account["username"]
        setup.api_mutation(client,"POST","/auth/login",{"email":account["email"],"password":passwords[name]},origin=ORIGIN)
        me=client.get("/api/v1/users/me").json()
        assert me["id"]==ids[name] and set(me["roles"])==set(account["roles"])
        assert client.get("/api/v1/admin/users").status_code==(200 if "ADMIN" in account["roles"] else 403)
        encoded=connection.scalar(select(User.password_hash).where(User.id==UUID(ids[name])))
        assert encoded.startswith("$argon2id$") and client.app.state.auth.verify_password(encoded,passwords[name])
        setup.api_mutation(client,"POST","/auth/logout",origin=ORIGIN)
    records=[]
    for u,p in connection.execute(select(User.__table__.c.id,Profile.__table__.c.display_name).join(Profile,Profile.user_id==User.id)):
        row=next(a for a in setup.ACCOUNTS if ids[a["username"]]==str(u))
        records.append({**row,"id":u,"status":"active"})
    before=(connection.scalar(select(func.count()).select_from(AuthSession)),len(audits))
    assert setup.apply_accounts(client,setup.account_plan(records,2),{},lambda ident:pytest.fail("No repeated bootstrap"),origin=ORIGIN)==ids
    assert before==(connection.scalar(select(func.count()).select_from(AuthSession)),connection.scalar(select(func.count()).select_from(AdminAuditLog)))

@pytest.mark.integration
def test_registration_cannot_choose_admin(auth):
    client,_=auth
    account={"username":"ordinary_user","email":"ordinary@example.com","display_name":"Ordinary","password":"Synthetic-ordinary-password!","roles":["ADMIN"]}
    with pytest.raises(RuntimeError, match="422"):
        setup.api_mutation(client,"POST","/auth/register",account,origin=ORIGIN)
    assert client.get("/api/v1/users/me").status_code == 401
    account.pop("roles")
    response=setup.api_mutation(client,"POST","/auth/register",account,origin=ORIGIN)
    assert response["roles"]==["USER"]
    setup.api_mutation(client,"POST","/auth/login",{"email":account["email"],"password":account["password"]},origin=ORIGIN)
    assert client.get("/api/v1/admin/users").status_code==403
