"""H04 Calibrated Performance Benchmark & Diagnostics Harness.

Measures:
1. DB Identity Guard (aurameme_test @ 127.0.0.1:55450, alembic 0020_follow_notifications)
2. Single-request SQL query counts across page_size 10/20/50/100 + hot/search/direct/comments
3. EXPLAIN (ANALYZE, BUFFERS) for core feed/search/direct/comment queries
4. Calibrated concurrent load ramp (1 -> 5 -> 10 -> 25 -> 50 -> 100 VUs) with:
   - Per-VU isolated httpx.AsyncClient + cookie jar
   - Pre-steady-state login
   - Fixed random seed + think time
   - Warm-up + steady-state measurement
   - Read/write mix + safe stop threshold
5. Session Lock Contention Probe (same session vs multi-session same user vs multi-user)
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from urllib.parse import urlparse

import httpx
import psutil
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from safety_guard import (
    DEFAULT_HARNESS_PORT,
    load_env_file,
    owned_uvicorn_server,
    verify_isolated_postgres,
    verify_runtime_env,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env.h01"
MANIFEST_FILE = BACKEND_DIR / "h01.local" / "seed_manifest.json"
USER_PASSWORD = "H01SimUser!2026"
BASE_URL = f"http://127.0.0.1:{DEFAULT_HARNESS_PORT}"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return round(ordered[lo] * (1 - frac) + ordered[hi] * frac, 2)


def measure_sql_counts(database_url: str, manifest: dict) -> dict:
    """Run in-process FastAPI TestClient with SQLAlchemy query counter."""
    os.environ["DATABASE_URL"] = database_url
    for k, v in load_env_file(ENV_FILE).items():
        os.environ.setdefault(k, v)
    sys.path.insert(0, str(BACKEND_DIR))
    from fastapi.testclient import TestClient
    from app.main import app

    results: dict[str, dict] = {}
    with TestClient(app, base_url=BASE_URL, headers={"Origin": "http://127.0.0.1:5173"}) as client:
        @contextmanager
        def count_queries():
            queries: list[str] = []

            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                queries.append(statement.strip().splitlines()[0][:120])

            event.listen(Engine, "before_cursor_execute", before_cursor_execute)
            try:
                yield queries
            finally:
                event.remove(Engine, "before_cursor_execute", before_cursor_execute)

        # Guest endpoints
        guest_cases = [
            ("feed_ps10_guest", "/api/v1/posts?page=1&page_size=10&include_interactions=true"),
            ("feed_ps20_guest", "/api/v1/posts?page=1&page_size=20&include_interactions=true"),
            ("feed_ps50_guest", "/api/v1/posts?page=1&page_size=50&include_interactions=true"),
            ("feed_ps100_guest", "/api/v1/posts?page=1&page_size=100&include_interactions=true"),
            ("feed_hot_ps20_guest", "/api/v1/posts?sort=reaction_desc&page=1&page_size=20&include_interactions=true"),
            ("feed_search_ps20_guest", "/api/v1/posts?search=Tu%20Tien&page=1&page_size=20&include_interactions=true"),
            ("post_direct_guest", f"/api/v1/posts/{manifest['post_1_id']}"),
            ("comments_ps20_guest", f"/api/v1/posts/{manifest['post_1_id']}/comments?page=1&page_size=20"),
        ]
        for name, path in guest_cases:
            with count_queries() as q:
                t0 = time.perf_counter()
                r = client.get(path)
                ms = round((time.perf_counter() - t0) * 1000, 2)
            results[name] = {
                "status": r.status_code,
                "sql_count": len(q),
                "elapsed_ms": ms,
                "items_count": len(r.json().get("items", [])) if r.status_code == 200 and "items" in r.json() else None,
            }

        # Authenticated user: get pre-session CSRF first, then login, then refresh CSRF
        pre_csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "sim_user_001@example.com", "password": USER_PASSWORD},
            headers={"X-CSRF-Token": pre_csrf},
        )
        if login_res.status_code != 200:
            raise RuntimeError(f"TestClient login failed: {login_res.status_code} {login_res.text}")

        auth_cases = [
            ("feed_ps10_auth", "/api/v1/posts?page=1&page_size=10&include_interactions=true"),
            ("feed_ps20_auth", "/api/v1/posts?page=1&page_size=20&include_interactions=true"),
            ("feed_ps50_auth", "/api/v1/posts?page=1&page_size=50&include_interactions=true"),
            ("feed_ps100_auth", "/api/v1/posts?page=1&page_size=100&include_interactions=true"),
            ("feed_hot_ps20_auth", "/api/v1/posts?sort=reaction_desc&page=1&page_size=20&include_interactions=true"),
            ("feed_search_ps20_auth", "/api/v1/posts?search=Tu%20Tien&page=1&page_size=20&include_interactions=true"),
            ("post_direct_auth", f"/api/v1/posts/{manifest['post_1_id']}"),
            ("comments_ps20_auth", f"/api/v1/posts/{manifest['post_1_id']}/comments?page=1&page_size=20"),
        ]
        for name, path in auth_cases:
            with count_queries() as q:
                t0 = time.perf_counter()
                r = client.get(path)
                ms = round((time.perf_counter() - t0) * 1000, 2)
            results[name] = {
                "status": r.status_code,
                "sql_count": len(q),
                "elapsed_ms": ms,
                "items_count": len(r.json().get("items", [])) if r.status_code == 200 and "items" in r.json() else None,
            }

    return results


def run_explain_analyze(database_url: str, manifest: dict) -> dict:
    engine = create_engine(database_url, pool_pre_ping=True)
    queries = {
        "feed_newest_ps20": """
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT p.id, p.title, p.created_at
            FROM posts p
            JOIN users u ON u.id = p.author_id
            JOIN profiles pr ON pr.user_id = u.id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.status = 'published' AND p.deleted_at IS NULL AND u.status = 'active'
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT 20 OFFSET 0
        """,
        "feed_search_ps20": """
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT p.id, p.title, p.created_at
            FROM posts p
            JOIN users u ON u.id = p.author_id
            JOIN profiles pr ON pr.user_id = u.id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.status = 'published' AND p.deleted_at IS NULL AND u.status = 'active'
              AND (p.title ILIKE '%Tu Tien%' OR p.content ILIKE '%Tu Tien%' OR pr.display_name ILIKE '%Tu Tien%' OR u.username ILIKE '%Tu Tien%')
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT 20 OFFSET 0
        """,
        "post_direct": f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT p.id, p.title
            FROM posts p
            JOIN users u ON u.id = p.author_id
            JOIN profiles pr ON pr.user_id = u.id
            WHERE p.id = '{manifest['post_1_id']}'::uuid
              AND p.status = 'published' AND p.deleted_at IS NULL AND u.status = 'active'
        """,
        "comments_ps20": f"""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT c.id, c.body, c.created_at
            FROM comments c
            JOIN users u ON u.id = c.author_id
            JOIN profiles pr ON pr.user_id = u.id
            WHERE c.post_id = '{manifest['post_1_id']}'::uuid
              AND c.status = 'visible' AND c.deleted_at IS NULL AND u.status = 'active'
            ORDER BY c.created_at ASC, c.id ASC
            LIMIT 20 OFFSET 0
        """,
    }
    out = {}
    with engine.connect() as conn:
        for name, sql in queries.items():
            lines = [row[0] for row in conn.execute(text(sql)).fetchall()]
            out[name] = lines
    engine.dispose()
    return out


async def login_vu(client: httpx.AsyncClient, email: str) -> str | None:
    pre = await client.get(f"{BASE_URL}/api/v1/auth/csrf")
    if pre.status_code != 200:
        return None
    pre_csrf = pre.json().get("csrf_token")
    r = await client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": USER_PASSWORD},
        headers={"X-CSRF-Token": pre_csrf},
    )
    if r.status_code != 200:
        return None
    c = await client.get(f"{BASE_URL}/api/v1/auth/csrf")
    if c.status_code == 200:
        return c.json().get("csrf_token")
    return None


async def run_load_stage(
    vu_count: int,
    warmup_s: float,
    steady_s: float,
    post_ids: list[str],
    seed: int,
) -> dict:
    rng = random.Random(seed + vu_count)
    # 50% authenticated VUs (up to 50 distinct sim_user_001..sim_user_100), 50% guest VUs
    clients: list[tuple[httpx.AsyncClient, str | None, int]] = []
    for idx in range(vu_count):
        client = httpx.AsyncClient(timeout=15.0, headers={"Origin": "http://127.0.0.1:5173"})
        csrf = None
        if idx % 2 == 0:
            user_num = (idx % 100) + 1
            csrf = await login_vu(client, f"sim_user_{user_num:03d}@example.com")
        clients.append((client, csrf, idx))

    latencies_ms: list[float] = []
    by_endpoint: dict[str, list[float]] = defaultdict(list)
    status_counts: dict[str, int] = defaultdict(int)
    errors = 0
    total_requests = 0
    stop_flag = False
    measure_start = time.perf_counter() + warmup_s
    measure_end = measure_start + steady_s

    async def vu_loop(client: httpx.AsyncClient, csrf: str | None, vu_idx: int):
        nonlocal errors, total_requests
        local_rng = random.Random(seed * 1000 + vu_idx)
        reactions = ["haha", "sad", "wow", "angry", "love"]
        while not stop_flag:
            now = time.perf_counter()
            if now >= measure_end:
                break
            roll = local_rng.random()
            pid = local_rng.choice(post_ids)
            t0 = time.perf_counter()
            ep_name = "feed_newest"
            try:
                if roll < 0.40:
                    ep_name = "feed_newest"
                    resp = await client.get(f"{BASE_URL}/api/v1/posts?page=1&page_size=20&include_interactions=true")
                elif roll < 0.55:
                    ep_name = "feed_hot"
                    resp = await client.get(f"{BASE_URL}/api/v1/posts?sort=reaction_desc&page=1&page_size=20&include_interactions=true")
                elif roll < 0.70:
                    ep_name = "feed_search"
                    resp = await client.get(f"{BASE_URL}/api/v1/posts?search=Tu%20Tien&page=1&page_size=20&include_interactions=true")
                elif roll < 0.85:
                    ep_name = "post_direct"
                    resp = await client.get(f"{BASE_URL}/api/v1/posts/{pid}")
                elif roll < 0.95:
                    ep_name = "comments"
                    resp = await client.get(f"{BASE_URL}/api/v1/posts/{pid}/comments?page=1&page_size=20")
                else:
                    if csrf:
                        ep_name = "write_reaction"
                        resp = await client.put(
                            f"{BASE_URL}/api/v1/posts/{pid}/reactions",
                            json={"reaction_type": local_rng.choice(reactions)},
                            headers={"X-CSRF-Token": csrf},
                        )
                    else:
                        ep_name = "feed_newest"
                        resp = await client.get(f"{BASE_URL}/api/v1/posts?page=1&page_size=20&include_interactions=true")
                elapsed = (time.perf_counter() - t0) * 1000.0
                if time.perf_counter() >= measure_start:
                    total_requests += 1
                    status_counts[str(resp.status_code)] += 1
                    if resp.status_code >= 500 or (resp.status_code >= 400 and resp.status_code not in (409, 429)):
                        errors += 1
                    latencies_ms.append(elapsed)
                    by_endpoint[ep_name].append(elapsed)
            except Exception as exc:
                if time.perf_counter() >= measure_start:
                    total_requests += 1
                    errors += 1
                    status_counts[type(exc).__name__] += 1
            await asyncio.sleep(local_rng.uniform(0.15, 0.35))

    await asyncio.gather(*(vu_loop(c, csrf, i) for c, csrf, i in clients))
    for c, _, _ in clients:
        await c.aclose()

    err_rate = round((errors / total_requests) * 100.0, 2) if total_requests else 0.0
    rps = round(total_requests / steady_s, 2) if steady_s > 0 else 0.0
    return {
        "vus": vu_count,
        "steady_seconds": steady_s,
        "total_requests": total_requests,
        "rps": rps,
        "errors": errors,
        "error_rate_pct": err_rate,
        "status_counts": dict(status_counts),
        "p50_ms": percentile(latencies_ms, 50),
        "p95_ms": percentile(latencies_ms, 95),
        "p99_ms": percentile(latencies_ms, 99),
        "max_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
        "by_endpoint_p95_ms": {k: percentile(v, 95) for k, v in by_endpoint.items()},
    }


async def run_session_lock_probe() -> dict:
    """Compare 10 concurrent GET /api/v1/posts requests under:
    A) Same session cookie (FOR UPDATE serializes requests)
    B) 10 separate sessions of same user (sim_user_001)
    C) 10 separate users (sim_user_001..010)
    """
    async def timed_get(client: httpx.AsyncClient) -> tuple[int, float]:
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/api/v1/posts?page=1&page_size=20&include_interactions=true")
        return r.status_code, (time.perf_counter() - t0) * 1000.0

    # A: same session
    c_same = httpx.AsyncClient(timeout=15.0, headers={"Origin": "http://127.0.0.1:5173"})
    await login_vu(c_same, "sim_user_001@example.com")
    t0 = time.perf_counter()
    res_a = await asyncio.gather(*(timed_get(c_same) for _ in range(10)))
    wall_a = round((time.perf_counter() - t0) * 1000.0, 2)
    await c_same.aclose()

    # B: 10 separate sessions, same user
    c_multi_sess = [httpx.AsyncClient(timeout=15.0, headers={"Origin": "http://127.0.0.1:5173"}) for _ in range(10)]
    await asyncio.gather(*(login_vu(c, "sim_user_001@example.com") for c in c_multi_sess))
    t0 = time.perf_counter()
    res_b = await asyncio.gather(*(timed_get(c) for c in c_multi_sess))
    wall_b = round((time.perf_counter() - t0) * 1000.0, 2)
    for c in c_multi_sess:
        await c.aclose()

    # C: 10 distinct users
    c_multi_user = [httpx.AsyncClient(timeout=15.0, headers={"Origin": "http://127.0.0.1:5173"}) for _ in range(10)]
    await asyncio.gather(*(login_vu(c_multi_user[i], f"sim_user_{i+1:03d}@example.com") for i in range(10)))
    t0 = time.perf_counter()
    res_c = await asyncio.gather(*(timed_get(c) for c in c_multi_user))
    wall_c = round((time.perf_counter() - t0) * 1000.0, 2)
    for c in c_multi_user:
        await c.aclose()

    return {
        "same_session_10": {
            "wall_ms": wall_a,
            "p95_ms": percentile([x[1] for x in res_a], 95),
            "statuses": [x[0] for x in res_a],
        },
        "multi_session_same_user_10": {
            "wall_ms": wall_b,
            "p95_ms": percentile([x[1] for x in res_b], 95),
            "statuses": [x[0] for x in res_b],
        },
        "multi_user_10": {
            "wall_ms": wall_c,
            "p95_ms": percentile([x[1] for x in res_c], 95),
            "statuses": [x[0] for x in res_c],
        },
    }


def collect_resource_snapshot(server_pid: int | None) -> dict:
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    server_info = None
    if server_pid:
        try:
            p = psutil.Process(server_pid)
            server_info = {
                "pid": server_pid,
                "rss_mb": round(p.memory_info().rss / (1024 * 1024), 2),
                "cpu_pct": p.cpu_percent(interval=0.1),
            }
        except psutil.NoSuchProcess:
            pass
    docker_stats = None
    try:
        out = subprocess.check_output(
            ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", "aurameme-h01-sim-pg"],
            text=True,
            timeout=5,
        ).strip()
        docker_stats = out
    except Exception:
        pass
    return {
        "host_cpu_pct": cpu,
        "host_ram_used_pct": mem.percent,
        "uvicorn": server_info,
        "postgres_docker_stats": docker_stats,
    }


async def main_async(args):
    env_vals = load_env_file(ENV_FILE)
    verify_runtime_env(env_vals)
    db_url = env_vals["DATABASE_URL"]
    db_identity = verify_isolated_postgres(db_url, MANIFEST_FILE)
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

    print("[1/5] Measuring SQL counts (in-process TestClient)...")
    sql_counts = measure_sql_counts(db_url, manifest)

    print("[2/5] Running EXPLAIN (ANALYZE, BUFFERS)...")
    explain_plans = run_explain_analyze(db_url, manifest)

    print(f"[3/5] Starting owned uvicorn server on 127.0.0.1:{DEFAULT_HARNESS_PORT} (workers=1)...")
    with owned_uvicorn_server(BACKEND_DIR, env_vals, port=DEFAULT_HARNESS_PORT) as (proc, _):
        async with httpx.AsyncClient(timeout=5.0) as hc:
            posts_r = await hc.get(f"{BASE_URL}/api/v1/posts?page=1&page_size=50")
            post_ids = [item["id"] for item in posts_r.json()["items"]]

        print("[4/5] Running Session Lock Contention Probe...")
        lock_probe = await run_session_lock_probe()

        print("[5/5] Running calibrated VU ramp...")
        stages = []
        stop_reason = None
        for vus in [1, 5, 10, 25, 50, 100]:
            print(f"  -> Stage {vus} VUs (warmup={args.warmup}s, steady={args.steady}s)...")
            stage = await run_load_stage(vus, args.warmup, args.steady, post_ids, seed=20261127)
            stage["resources"] = collect_resource_snapshot(proc.pid)
            stages.append(stage)
            print(f"     rps={stage['rps']}, p50={stage['p50_ms']}ms, p95={stage['p95_ms']}ms, p99={stage['p99_ms']}ms, err={stage['error_rate_pct']}%")
            if stage["error_rate_pct"] > 5.0 or stage["p95_ms"] > 5000.0:
                stop_reason = f"Safe stop triggered at {vus} VUs (error_rate={stage['error_rate_pct']}%, p95={stage['p95_ms']}ms)"
                print(f"  !! {stop_reason}")
                break

    report = {
        "phase": args.phase,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "db_identity": db_identity,
        "methodology": {
            "seed": 20261127,
            "warmup_s": args.warmup,
            "steady_s": args.steady,
            "think_time_s": [0.15, 0.35],
            "workers": 1,
            "db_pool": {"pool_size": 10, "max_overflow": 20, "pool_timeout": 15},
            "workload_mix": {
                "feed_newest": "40%",
                "feed_hot": "15%",
                "feed_search": "15%",
                "post_direct": "15%",
                "comments": "10%",
                "write_reaction_auth": "5%",
            },
            "stop_reason": stop_reason,
        },
        "sql_counts": sql_counts,
        "explain_analyze": explain_plans,
        "session_lock_probe": lock_probe,
        "stages": stages,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved report to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=["before", "after"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--steady", type=float, default=20.0)
    asyncio.run(main_async(parser.parse_args()))
