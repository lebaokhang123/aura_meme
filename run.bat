@echo off
setlocal DisableDelayedExpansion
set "AURAMEME_MODE=demo"
if /I "%~1"=="demo" set "AURAMEME_MODE=demo"
if /I "%~1"=="dev" set "AURAMEME_MODE=dev"
if not "%~1"=="" if /I not "%~1"=="demo" if /I not "%~1"=="dev" (
  echo Cach dung: run.bat [demo / dev]
  pause
  exit /b 1
)
if not "%~2"=="" (
  echo Cach dung: run.bat [demo / dev]
  pause
  exit /b 1
)
set "AURAMEME_LAUNCHER=%~f0"
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo Loi: Thieu backend\.venv\Scripts\python.exe. Xem README de tao virtual environment.
  pause
  exit /b 1
)
pushd "%~dp0" || exit /b 1
"%~dp0backend\.venv\Scripts\python.exe" -I -c "import os; from pathlib import Path; p=Path(os.environ['AURAMEME_LAUNCHER']); exec(compile(p.read_text(encoding='utf-8').split('\n# AURAMEME_PYTHON\n',1)[1],str(p),'exec'),{'__name__':'__main__','__file__':str(p)})"
set "AURAMEME_EXIT=%errorlevel%"
popd
if not "%AURAMEME_EXIT%"=="0" pause
exit /b %AURAMEME_EXIT%
# AURAMEME_PYTHON
"""Windows-only supervisor embedded here to keep the launcher self-contained."""
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'
URL = 'http://localhost:5173'
DEMO = os.environ.get('AURAMEME_MODE') == 'demo'
sys.path.insert(0, str(BACKEND))
BOOTSTRAP = "import os; from pathlib import Path; p=Path(os.environ['AURAMEME_LAUNCHER']); exec(compile(p.read_text(encoding='utf-8').split('\\n# AURAMEME_PYTHON\\n',1)[1],str(p),'exec'),{'__name__':'__main__','__file__':str(p)})"


class LaunchError(Exception):
    pass


# Microsoft Job Objects: children inherit membership; only this launcher's tree is owned.
class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
        ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('active_limit',w.DWORD),
        ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]


class JobLimits(ctypes.Structure):
    _fields_ = [('basic',BasicLimits),('io',ctypes.c_uint64*6),('process_memory',ctypes.c_size_t),
        ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]


def windows():
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateMutexW':([ctypes.c_void_p,w.BOOL,w.LPCWSTR],w.HANDLE),
        'CreateJobObjectW':([ctypes.c_void_p,w.LPCWSTR],w.HANDLE),
        'SetInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),
        'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),
        'GetCurrentProcess':([],w.HANDLE),
        'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
        'IsProcessInJob':([w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
        'CloseHandle':([w.HANDLE],w.BOOL),
    }
    for name,(args,result) in signatures.items():
        getattr(api,name).argtypes = args
        getattr(api,name).restype = result
    return api


def claim_launcher(api):
    name = 'Local\\AuraMeme-' + hashlib.sha256(os.path.normcase(str(ROOT)).encode()).hexdigest()[:24]
    mutex = api.CreateMutexW(None,False,name)
    error = ctypes.get_last_error()
    if not mutex:
        raise LaunchError('Không tạo được khóa launcher Windows. Chưa khởi động dịch vụ.')
    if error == 183:
        raise LaunchError('Launcher AuraMeme đang chạy. Không mở thêm server; dùng cửa sổ launcher hiện có.')
    job = api.CreateJobObjectW(None,None)
    limits = JobLimits()
    # KILL_ON_JOB_CLOSE; BREAKAWAY_OK is used only by the browser helper, not servers.
    limits.basic.flags = 0x2000 | 0x800
    if (not job or not api.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits))
            or not api.AssignProcessToJobObject(job,api.GetCurrentProcess())):
        raise LaunchError('Không tạo được nhóm tiến trình Windows an toàn. Chưa khởi động dịch vụ.')
    # Keep these non-inheritable handles alive until process exit, including console close.
    return mutex,job


def listeners():
    result = subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/netstat.exe'),'-ano'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=5,check=True)
    ports = {8000:set(),5173:set()}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 5 and fields[0] == 'TCP' and fields[3] == 'LISTENING':
            port = int(fields[1].rsplit(':',1)[1])
            if port in ports:
                ports[port].add(int(fields[4]))
    return ports


def owned(api,job,pid):
    handle = api.OpenProcess(0x1000,False,pid)
    if not handle:
        return False
    try:
        answer = w.BOOL()
        return bool(api.IsProcessInJob(handle,job,ctypes.byref(answer)) and answer.value)
    finally:
        api.CloseHandle(handle)


def prerequisites():
    if sys.version_info < (3,12):
        raise LaunchError('Cần Python 3.12 trở lên trong backend\\.venv.')
    node = shutil.which('node')
    if not node or not shutil.which('npm'):
        raise LaunchError('Thiếu Node.js hoặc npm trong PATH. Cài môi trường theo README rồi mở lại launcher.')
    result = subprocess.run([node,'--version'],capture_output=True,text=True,timeout=5,check=True)
    if tuple(map(int,result.stdout.strip().lstrip('v').split('.')[:2])) < (22,12):
        raise LaunchError('Cần Node.js 22.12 trở lên.')
    package = json.loads((FRONTEND/'package.json').read_text(encoding='utf-8'))
    packages = list(package['dependencies']) + list(package['devDependencies'])
    if any(not (FRONTEND/'node_modules'/name/'package.json').is_file() for name in packages):
        raise LaunchError('Thiếu dependency frontend. Từ frontend chạy npm ci rồi mở lại launcher.')
    try:
        if DEMO:
            from app.demo import activate_demo
            activate_demo()
        from app.config import AuthSettings, CatalogSettings, MediaSettings, load_settings
        from app.main import app
        from sqlalchemy.engine import make_url
        settings,auth = load_settings(),AuthSettings()
        MediaSettings();CatalogSettings()
        target = make_url(settings.database_url.get_secret_value())
    except ImportError:
        raise LaunchError('Thiếu dependency backend. Cài dependency vào backend\\.venv theo README.') from None
    except Exception:
        raise LaunchError('Cấu hình backend không hợp lệ. Kiểm tra các trường trong backend/.env theo README; không chia sẻ giá trị bí mật.') from None
    if target.database != ('aurameme_demo' if DEMO else 'aurameme_dev') or target.host not in {'localhost','127.0.0.1','::1'}:
        raise LaunchError('Launcher chỉ dùng PostgreSQL local aurameme_demo (demo) hoặc aurameme_dev (dev) đúng chế độ. Không dùng test/E2E làm demo.')
    if auth.auth_environment != 'development' or URL not in auth.auth_allowed_origins:
        raise LaunchError('HTTP local cần AUTH_ENVIRONMENT=development và AUTH_ALLOWED_ORIGINS có http://localhost:5173. Launcher không tự sửa cấu hình.')
    return node


def database_probe():
    from sqlalchemy import inspect,text
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.config import Settings
    from app.db import create_db_engine
    from app.models import Base
    engine = create_db_engine(Settings(db_connect_timeout=3))
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            connection.exec_driver_sql("SET LOCAL statement_timeout = '3000ms'")
            assert connection.scalar(text('SELECT current_database()')) == ('aurameme_demo' if DEMO else 'aurameme_dev')
            assert connection.scalar(text('SELECT current_schema()')) == 'public'
            if DEMO:
                from app.demo import demo_connection
                demo_connection(connection)
            assert connection.scalar(text('SELECT 1')) == 1
            tables = set(inspect(connection).get_table_names())
            schema = 'empty' if not tables else 'mismatch'
            if tables == set(Base.metadata.tables) | {'alembic_version'}:
                head = ScriptDirectory.from_config(Config(str(BACKEND/'alembic.ini'))).get_current_head()
                if connection.scalar(text('SELECT version_num FROM alembic_version')) == head:
                    schema = 'ready'
                    if DEMO:
                        from alembic.autogenerate import compare_metadata
                        from alembic.migration import MigrationContext
                        if head != '0009_vault_open' or compare_metadata(MigrationContext.configure(
                                connection, opts={'compare_server_default': True}), Base.metadata):
                            schema = 'mismatch'
            print(json.dumps({'schema':schema}))
    finally:
        engine.dispose()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def wait_ready(children,api,job):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for name,process in children:
            if process.poll() is not None:
                raise LaunchError(name + ' không khởi động được. Kiểm tra dependency/cấu hình/cổng theo README.')
        try:
            ports = listeners()
            if all(ports.values()):
                if not all(owned(api,job,pid) for pids in ports.values() for pid in pids):
                    raise LaunchError('Cổng đã bị tiến trình khác chiếm trong lúc khởi động. Không mở trình duyệt.')
                with opener.open('http://127.0.0.1:8000/health',timeout=1) as response:
                    assert response.status == 200 and json.loads(response.read(1024)) == {'status':'ok'}
                with opener.open(URL,timeout=1) as response:
                    assert response.status == 200 and b'id="root"' in response.read(16384)
                return
        except (OSError,ValueError,AssertionError):
            pass
        time.sleep(.25)
    raise LaunchError('Quá 30 giây chờ HTTP sẵn sàng. Chỉ dừng các dịch vụ do launcher này tạo.')


def open_browser():
    # A breakaway helper keeps the user's browser outside the server cleanup job.
    environment = {k:v for k,v in os.environ.items() if not k.startswith('AUTH_') and not k.endswith('DATABASE_URL')}
    try:
        subprocess.run([sys.executable,'-I','-c',"import sys,webbrowser; sys.exit(0 if webbrowser.open('http://localhost:5173') else 1)"],
            env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB | subprocess.CREATE_NO_WINDOW,timeout=5,check=True)
    except (OSError,subprocess.SubprocessError):
        print('Không tự mở được trình duyệt ngoài nhóm server; hãy mở ' + URL,flush=True)


def main():
    children = []
    try:
        api = windows()
        handles = claim_launcher(api)
        node = prerequisites()
        ports = listeners()
        occupied = [str(port) for port,pids in ports.items() if pids]
        if occupied:
            raise LaunchError('Cổng ' + ', '.join(occupied) + ' đang được dùng. Không chiếm cổng hoặc dừng tiến trình khác.')
        print('CHẾ ĐỘ: ' + ('DEMO — aurameme_demo' if DEMO else 'DEV — aurameme_dev'),flush=True)
        print('Đang kiểm tra PostgreSQL read-only...',flush=True)
        try:
            probe = subprocess.run([sys.executable,'-I','-c',BOOTSTRAP,'--database-probe'],cwd=BACKEND,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=12,check=True,text=True)
            schema = json.loads(probe.stdout)['schema']
        except Exception:
            raise LaunchError('Không kết nối được PostgreSQL. Kiểm tra Docker/dịch vụ, kết nối và cấu hình local; launcher không tự reset hoặc khởi tạo DB.') from None
        if schema == 'mismatch' or (DEMO and schema != 'ready'):
            raise LaunchError('Schema database không khớp phiên bản hiện tại. Dừng để Owner review; không tự migration.')
        if schema == 'empty':
            raise LaunchError('aurameme_dev chưa có schema, không mở website với API lỗi. Chạy run.bat demo để dùng bản local có schema. Không tự migrate/seed.')
        for name,command,cwd in [
            ('Backend',[sys.executable,'-I','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'],BACKEND),
            ('Frontend',[node,str(FRONTEND/'node_modules/vite/bin/vite.js'),'--host','localhost','--port','5173','--strictPort','--mode','development'],FRONTEND),
        ]:
            environment = os.environ.copy() if name == 'Backend' else {
                k:v for k,v in os.environ.items() if not k.startswith('AUTH_') and not k.endswith('DATABASE_URL')
                and k not in {'MEDIA_STORAGE_ROOT','CATALOG_STORAGE_ROOT'}}
            children.append((name,subprocess.Popen(command,cwd=cwd,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)))
        wait_ready(children,api,handles[1])
        print('SẴN SÀNG' + (' [DEMO aurameme_demo]' if DEMO else '') + ': Backend http://127.0.0.1:8000 | Frontend ' + URL,flush=True)
        print('Nhấn Enter hoặc Ctrl+C trong cửa sổ này để dừng. Đóng cửa sổ cũng dừng cây server của launcher, không dừng ứng dụng khác.',flush=True)
        open_browser()
        stop = threading.Event()
        def read_stop():
            try:
                input()
            except EOFError:
                pass
            stop.set()
        threading.Thread(target=read_stop,daemon=True).start()
        while not stop.wait(.25):
            if any(process.poll() is not None for _,process in children):
                raise LaunchError('Một dịch vụ đã dừng bất thường. Dừng nhóm launcher; kiểm tra môi trường rồi mở lại.')
        return 0
    except KeyboardInterrupt:
        print('\nĐang dừng AuraMeme...',flush=True)
        return 0
    except LaunchError as error:
        print('LỖI: ' + str(error),flush=True)
        return 1
    except Exception:
        print('LỖI: Không khởi động được launcher. Kiểm tra môi trường/cấu hình theo README; không chia sẻ secrets.',flush=True)
        return 1
    finally:
        for _,process in reversed(children):
            if process.poll() is None:
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                except OSError:
                    pass
        for _,process in children:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass  # OS job cleanup on this process's exit also covers grandchildren.


if __name__ == '__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    if sys.argv[1:] == ['--database-probe']:
        try:
            if DEMO:
                from app.demo import activate_demo
                activate_demo()
            database_probe()
        except Exception:
            sys.exit(1)
    else:
        sys.exit(main())
