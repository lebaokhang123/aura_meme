"""Owner-confirmed, idempotent demo accounts through the existing Auth/Admin APIs."""
import argparse
from getpass import getpass
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.demo import DEMO_ROOT, activate_demo, bootstrap_admin, demo_connection, demo_environment, validate_demo_url, reviewed_demo_schema
from app.db import create_db_engine
from app.models import Profile, Role, User, UserRole

ACCOUNTS=(
    {"username":"khang_dev","email":"khang_dev@example.com","display_name":"Khang Dev","roles":["ADMIN","USER"]},
    {"username":"kien_dev","email":"kien_dev@example.com","display_name":"Kien Dev","roles":["ADMIN","USER"]},
    {"username":"gigachad","email":"gigachad@example.com","display_name":"Gigachad","roles":["USER"]},
)
CONFIRMATION="aurameme_demo khang_dev"

def account_plan(records,active_admins):
    accounts=[];conflicts=[]
    for wanted in ACCOUNTS:
        found=[r for r in records if r["username"]==wanted["username"] or r["email"].lower()==wanted["email"]]
        existing=found[0] if len(found)==1 else None
        if len(found)>1 or existing and (existing["username"]!=wanted["username"] or existing["email"].lower()!=wanted["email"] or existing["display_name"]!=wanted["display_name"] or existing["status"]!="active" or set(existing["roles"])-set(wanted["roles"]) or "USER" not in existing["roles"]):
            conflicts.append(wanted["username"])
        roles=existing["roles"] if existing else []
        accounts.append({**wanted,"id":str(existing["id"]) if existing else None,"create":existing is None,
                         "grant_admin":"ADMIN" in wanted["roles"] and "ADMIN" not in roles})
    if accounts[0]["grant_admin"] and active_admins:
        conflicts.append("An administrator already exists; first-admin bootstrap is forbidden.")
    return {"accounts":accounts,"bootstrap":accounts[0]["grant_admin"] and active_admins==0,
            "conflicts":conflicts,"writes":any(r["create"] or r["grant_admin"] for r in accounts)}

def read_plan(engine):
    with engine.connect() as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        demo_connection(connection)
        reviewed_demo_schema(connection)
        names=[u["username"] for u in ACCOUNTS];emails=[u["email"] for u in ACCOUNTS]
    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        records=[]
        for user,profile in db.execute(select(User,Profile).join(Profile,Profile.user_id==User.id).where(or_(User.username.in_(names),User.email.in_(emails)))):
            roles=list(db.scalars(select(Role.code).join(UserRole).where(UserRole.user_id==user.id).order_by(Role.code)))
            records.append({"id":user.id,"username":user.username,"email":user.email,"display_name":profile.display_name,"status":user.status,"roles":roles})
        admins=db.scalar(text("SELECT count(DISTINCT u.id) FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id WHERE r.code='ADMIN' AND u.status='active'"))
    return account_plan(records,admins)

def api_mutation(client,method,path,payload=None,origin="http://localhost:5173"):
    csrf=client.get("/api/v1/auth/csrf")
    if csrf.status_code!=200:raise RuntimeError("CSRF request refused.")
    response=client.request(method,"/api/v1"+path,json=payload,headers={"Origin":origin,"X-CSRF-Token":csrf.json()["csrf_token"]})
    if response.status_code not in {200,201,204}:raise RuntimeError("Account API refused request: "+str(response.status_code))
    return response.json() if response.status_code!=204 else None

def apply_accounts(client,plan,passwords,bootstrap,origin="http://localhost:5173"):
    def mutate(method,path,payload=None):return api_mutation(client,method,path,payload,origin)
    if plan["conflicts"]:raise ValueError("Account conflicts; no changes allowed.")
    ids={r["username"]:r["id"] for r in plan["accounts"]}
    for row in plan["accounts"]:
        if row["create"]:
            created=mutate("POST","/auth/register",{k:row[k] for k in ("username","email","display_name")}|{"password":passwords[row["username"]]})
            if created["username"]!=row["username"] or created["roles"]!=["USER"]:raise RuntimeError("Unexpected registration result.")
            ids[row["username"]]=created["id"]
    if plan["bootstrap"]:bootstrap(ids["khang_dev"])
    second=plan["accounts"][1]
    if second["grant_admin"]:
        logged_in=False
        try:
            mutate("POST","/auth/login",{"email":ACCOUNTS[0]["email"],"password":passwords["khang_dev"]});logged_in=True
            me=client.get("/api/v1/users/me")
            if me.status_code!=200 or me.json()["id"]!=ids["khang_dev"] or "ADMIN" not in me.json()["roles"]:
                raise RuntimeError("Acting administrator identity mismatch.")
            result=mutate("PUT","/admin/users/"+ids["kien_dev"]+"/roles",{"roles":["USER","ADMIN"]})
            if set(result["roles"])!={"USER","ADMIN"}:raise RuntimeError("Admin role grant refused.")
        finally:
            if logged_in:mutate("POST","/auth/logout")
    return ids

def main(argv=None,ask=input,password=getpass):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root",type=Path,default=DEMO_ROOT)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv);engine=None
    try:
        values=demo_environment(args.config_root)
        engine=create_db_engine(validate_demo_url(values["DATABASE_URL"]))
        plan=read_plan(engine);print(json.dumps(plan,ensure_ascii=False,indent=2))
        if plan["conflicts"]:print("Conflicts found. No changes.");return 1
        if not args.apply or not plan["writes"]:return 0
        if password is getpass and not sys.stdin.isatty():
            print("Use an interactive local terminal; passwords cannot be piped or passed as arguments.");return 1
        print("Only the listed accounts/roles will change. Existing passwords and unrelated users are preserved.")
        if ask('Type "'+CONFIRMATION+'" to create accounts and grant the listed Admin roles: ')!=CONFIRMATION:
            print("Cancelled: confirmation phrase did not match. No changes.");return 1
        print("Passwords must contain 12-128 characters. Each password is entered twice and remains hidden.")
        passwords={}
        for row in plan["accounts"]:
            if row["create"]:
                value=password("New password for "+row["username"]+": ")
                if not 12<=len(value)<=128 or value!=password("Confirm password for "+row["username"]+": "):
                    print("Invalid/mismatched password. No changes.");return 1
                passwords[row["username"]]=value
        if plan["accounts"][1]["grant_admin"] and "khang_dev" not in passwords:
            passwords["khang_dev"]=password("Current Khang Dev password for audited Admin API: ")
        if read_plan(engine)!=plan:print("Demo changed while confirming. Run plan again; no changes.");return 1
        activate_demo(args.config_root)
        from fastapi.testclient import TestClient
        from app.main import app
        def first_admin(ident):
            with Session(engine) as db,db.begin():
                db.execute(text("SET LOCAL lock_timeout='5s'"));demo_connection(db.connection())
                bootstrap_admin(db,UUID(ident),lambda prompt:CONFIRMATION)
        with TestClient(app,base_url="http://localhost:8000") as client:
            apply_accounts(client,plan,passwords,first_admin)
        passwords.clear()
        final=read_plan(engine)
        if final["conflicts"] or final["writes"]:raise RuntimeError("Final account state requires review.")
        print("Setup complete. Stable account IDs and roles:")
        print(json.dumps(final["accounts"],ensure_ascii=False,indent=2))
        return 0
    except (EOFError,KeyboardInterrupt):print("Cancelled.");return 1
    except Exception:
        print("Setup refused or failed. No reset/cleanup performed. Run the read-only plan again to inspect partial progress.");return 1
    finally:
        if engine is not None:engine.dispose()

if __name__=="__main__":raise SystemExit(main())
