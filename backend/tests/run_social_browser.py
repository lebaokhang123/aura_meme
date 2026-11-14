"""Social browser on explicitly selected empty test/E2E only; never migrate/reset."""
from pathlib import Path
import os,sys,json,secrets,socket,subprocess,tempfile,time,urllib.request,io
from contextlib import redirect_stdout
from uuid import UUID
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import create_engine,select,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from run_browser import inventory
from app.models import Base,User,Role,MediaUpload
from app.demo import bootstrap_admin
from app.demo_accounts import ACCOUNTS,CONFIRMATION,account_plan,apply_accounts,api_mutation

PASSWORD="Synthetic-browser-password!"

def browser_target(config,e2e=False):
    database,role=("aurameme_e2e","aurameme_e2e_app") if e2e else ("aurameme_test","aurameme_test")
    url=dotenv_values(Path(config),interpolate=False).get("E2E_DATABASE_URL" if e2e else "TEST_DATABASE_URL","")
    assert url,"Explicit target URL required; no fallback"
    target=make_url(url)
    assert (target.database,target.username)==(database,role) and target.host in {"localhost","127.0.0.1"} and target.port in {None,5432} and not target.query
    return url,database,role


def main():
    assert len(sys.argv) in {2,3} and (len(sys.argv)==2 or sys.argv[2]=="--e2e"),"Provide private config [--e2e]; explicit test/E2E only"
    e2e=len(sys.argv)==3
    url,database,role=browser_target(sys.argv[1],e2e)
    engine=create_engine(url,poolclass=NullPool,hide_parameters=True,connect_args={"connect_timeout":3})
    with engine.connect() as c:
        c.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert c.scalar(text("SELECT current_user"))==role
        assert not any(c.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one())
        assert not c.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid!=pg_backend_pid()"))
        assert not any(inventory(c,database).values()),"Existing test rows; refuse"
        before=c.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY relname")).all()
    for port in (8001,4187):
        with socket.socket() as probe:probe.bind(("127.0.0.1",port))
    api=None;ids={};result=1
    with tempfile.TemporaryDirectory(prefix="aurameme-social-browser-") as private:
        media=Path(private)/"media";media.mkdir()
        from PIL import Image
        fixtures=Path(private)/"fixtures";fixtures.mkdir()
        image=Image.new("RGB",(24,24),(120,80,220))
        for ext,fmt in (("png","PNG"),("jpg","JPEG"),("webp","WEBP")):image.save(fixtures/("fixture."+ext),format=fmt)
        image.save(fixtures/"fixture.gif",format="GIF",save_all=True,append_images=[Image.new("RGB",(24,24),(220,80,120))],duration=100,loop=0)
        env=os.environ|{"DATABASE_URL":url,"TEST_DATABASE_URL":"" if e2e else url,"E2E_DATABASE_URL":url if e2e else "","AUTH_SIGNING_KEY":secrets.token_hex(32),
          "AUTH_ENVIRONMENT":"development","AUTH_ALLOWED_ORIGINS":json.dumps(["http://localhost:4187"]),
          "MEDIA_STORAGE_ROOT":str(media),"CATALOG_STORAGE_ROOT":str(Path(private)/"catalog"),
          "AURAMEME_API_TARGET":"http://127.0.0.1:8001","AURA_SOCIAL_E2E":"1","AURA_SOCIAL_FIXTURES":str(fixtures)}
        os.environ.update(env)
        try:
            from fastapi.testclient import TestClient
            from app.main import app
            def first_admin(ident):
                with Session(engine) as db,db.begin(),redirect_stdout(io.StringIO()):bootstrap_admin(db,UUID(ident),lambda prompt:CONFIRMATION)
            with TestClient(app,base_url="http://localhost:8001") as client:
                ids=apply_accounts(client,account_plan([],0),{a["username"]:PASSWORD for a in ACCOUNTS},first_admin,origin="http://localhost:4187")
                api_mutation(client,"POST","/auth/login",{"email":ACCOUNTS[0]["email"],"password":PASSWORD},origin="http://localhost:4187")
                for slug in ("gaming","anime","cong-nghe","truong-hoc","random"):
                    api_mutation(client,"POST","/admin/categories",{"slug":slug,"name":slug},origin="http://localhost:4187")
                api_mutation(client,"POST","/auth/logout",origin="http://localhost:4187")
            for flow in ("identity","crud","media","admin","pagination","profile-contact"):
                api=subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8001"],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                for _ in range(100):
                    if api.poll() is not None:raise RuntimeError("Owned API stopped")
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:8001/health",timeout=1) as response:assert response.status==200
                        break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError("API health timeout")
                result=subprocess.run(["npx.cmd" if os.name=="nt" else "npx","playwright","test","--config=../.github/playwright.social-real.config.mjs","--grep",flow,"--forbid-only"],cwd=ROOT.parent/"frontend",env=env).returncode
                api.terminate();api.wait(timeout=10);api=None
                if result:break
        finally:
            if api is not None and api.poll() is None:api.terminate();api.wait(timeout=10)
            with engine.begin() as c:
                counts=inventory(c,database)
                users=c.execute(select(User.id,User.username,User.email)).all()
                expected={a["username"]:a["email"] for a in ACCOUNTS}
                assert all(r.username in expected and r.email==expected[r.username] for r in users),"Unknown identity; refuse cleanup"
                owned=[r.id for r in users]
                assert all(r.code in {"USER","ADMIN"} for r in c.execute(select(Role.code)))
                allowed={"users","profiles","roles","user_roles","auth_sessions","categories","posts","comments","post_reactions","comment_reactions","media_uploads","admin_audit_logs","contact_messages"}
                assert not any(count for name,count in counts.items() if name not in allowed),"Unrelated data; refuse cleanup"
                for name,column in (("contact_messages","user_id"),("posts","author_id"),("comments","author_id"),("post_reactions","user_id"),("comment_reactions","user_id"),("media_uploads","owner_id"),("admin_audit_logs","actor_id"),("profiles","user_id"),("user_roles","user_id"),("auth_sessions","user_id")):
                    table=Base.metadata.tables[name]
                    assert all(v in owned for v in c.scalars(select(table.c[column]))),"Unknown owner; refuse cleanup"
                contact=Base.metadata.tables['contact_messages']
                assert all(row.body=='Synthetic Profile Contact E2E message' for row in c.execute(select(contact))),"Unexpected Contact content; refuse cleanup"
                uploads=c.execute(select(MediaUpload.object_key)).scalars().all()
                assert {p.name for p in media.iterdir()}==set(uploads),"Unexpected private media"
                for name in ("contact_messages","comment_reactions","post_reactions","comments","posts","media_uploads","admin_audit_logs","categories","auth_sessions","user_roles","profiles","users","roles"):
                    table=Base.metadata.tables[name]
                    if "user_id" in table.c:condition=table.c.user_id.in_(owned)
                    elif "author_id" in table.c:condition=table.c.author_id.in_(owned)
                    elif "owner_id" in table.c:condition=table.c.owner_id.in_(owned)
                    elif "actor_id" in table.c:condition=table.c.actor_id.in_(owned)
                    elif name=="users":condition=table.c.id.in_(owned)
                    else:
                        # The empty preflight and exact five fixtures establish ownership of these rows.
                        if name=="categories":assert all(v in {"gaming","anime","cong-nghe","truong-hoc","random"} for v in c.scalars(select(table.c.slug)))
                        known=list(c.scalars(select(table.c.id)));condition=table.c.id.in_(known)
                    c.execute(table.delete().where(condition))
                assert not any(inventory(c,database).values())
                assert c.execute(text("SELECT oid,relname,relfilenode FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY relname")).all()==before
            engine.dispose()
            print("Social browser cleanup PASS:"+database+"/public0010,29 empty tables; original schema/object IDs unchanged.")
    return result

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as error:
        print("Social browser stopped:",type(error).__name__,"No reset performed.",file=sys.stderr)
        raise SystemExit(1)
