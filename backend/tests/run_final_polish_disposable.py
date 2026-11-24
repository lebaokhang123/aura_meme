"""Run Final Polish tests on PostgreSQL disposable instances; no host ports are exposed."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

SUITE = "tests/test_checkpoint3_khang_vault.py"
COMMITTED = (
    "test_postgres_khang_dev_concurrent_grant",
    "test_postgres_khang_dev_concurrent_publication",
    "test_postgres_khang_dev_concurrent_vault_open",
    "test_postgres_khang_dev_concurrent_admin_approval",
    "test_postgres_cli_dry_run_and_execute[policy]",
    "test_postgres_cli_dry_run_and_execute[no-policy]",
)
REGRESSIONS = (
    "tests/test_vault_v1_runtime.py",
    "tests/test_vault_exp_award.py",
    "tests/test_inventory.py",
    "tests/test_catalog_publication.py",
    "tests/test_admin_workspace.py",
    "tests/test_aura_v1_runtime.py",
)
BACKEND = Path(__file__).resolve().parents[1]
LABEL = "io.aurameme.final-polish-test"


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, **kwargs)


def run_disposable(image, regressions):
    token = secrets.token_hex(16)
    name = "aurameme-fp-" + token
    password = secrets.token_hex(24)
    env = {**os.environ, "POSTGRES_PASSWORD": secrets.token_hex(24)}
    container_id = docker(
        "run", "--detach", "--rm", "--network", "none", "--name", name,
        "--label", f"{LABEL}={token}", "--env", "POSTGRES_PASSWORD", "postgres:17",
        "-c", "listen_addresses=127.0.0.1", "-c", f"cluster_name={name}",
        env=env, capture_output=True, text=True,
    ).stdout.strip()

    def query(sql):
        docker("exec", "-i", container_id, "psql", "-X", "-U", "postgres", "-d", "postgres",
               "-v", "ON_ERROR_STOP=1", input=sql, text=True, stdout=subprocess.DEVNULL)

    def isolated(*args):
        docker(
            "run", "--rm", "--network", f"container:{container_id}", "--workdir", "/source/backend",
            "--mount", f"type=bind,source={BACKEND},target=/source/backend,readonly",
            "--env", "TEST_DATABASE_URL", "--env", "AURAMEME_DISPOSABLE_TEST_CLUSTER",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "EMAIL_MODE=disabled", "--env", "EMAIL_VERIFICATION_REQUIRED=false",
            "--env", "DATABASE_URL=postgresql+psycopg://fixture:unused@127.0.0.1:1/fixture",
            image, "python", *args,
            env={**os.environ,
                 "TEST_DATABASE_URL": f"postgresql+psycopg://aurameme_test:{password}@127.0.0.1:5432/aurameme_test",
                 "AURAMEME_DISPOSABLE_TEST_CLUSTER": name},
        )

    try:
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", container_id, "pg_isready", "-h", "127.0.0.1"],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")

        query(f"CREATE ROLE aurameme_test LOGIN PASSWORD '{password}';\n"
              "CREATE DATABASE aurameme_test OWNER aurameme_test;\n")
        isolated("-m", "alembic", "upgrade", "head")
        query("CREATE DATABASE aurameme_fp_template WITH TEMPLATE aurameme_test OWNER postgres;\n")
        selected = " or ".join(dict.fromkeys(node.split("[")[0] for node in COMMITTED))
        isolated("-m", "pytest", "-q", "-p", "no:cacheprovider", SUITE, "-k", f"not ({selected})")
        for node in COMMITTED:
            query("DROP DATABASE aurameme_test;\n"
                  "CREATE DATABASE aurameme_test WITH TEMPLATE aurameme_fp_template OWNER aurameme_test;\n")
            isolated("-m", "pytest", "-q", "-p", "no:cacheprovider", f"{SUITE}::{node}")
        if regressions:
            query("DROP DATABASE aurameme_test;\n"
                  "CREATE DATABASE aurameme_test WITH TEMPLATE aurameme_fp_template OWNER aurameme_test;\n")
            isolated("-m", "pytest", "-q", "-p", "no:cacheprovider", *REGRESSIONS)
    finally:
        info = json.loads(docker("inspect", container_id, capture_output=True, text=True).stdout)[0]
        if info["Id"] != container_id or info["Config"]["Labels"].get(LABEL) != token:
            raise RuntimeError("Refusing to stop a container outside this run")
        docker("stop", container_id, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Local Python image with requirements-ci.txt installed")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--regressions", action="store_true", help="Run related suites after the last isolated run")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    docker("image", "inspect", args.image, stdout=subprocess.DEVNULL)
    for index in range(args.repeat):
        print(f"Disposable PostgreSQL acceptance run {index + 1}/{args.repeat}", flush=True)
        run_disposable(args.image, args.regressions and index == args.repeat - 1)


if __name__ == "__main__":
    main()
