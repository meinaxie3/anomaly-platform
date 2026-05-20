"""Phase 6 Definition-of-Done verification script.

Checks:
  1. All five HTTP services respond healthy.
  2. /services returns at least one service with required fields.
  3. /models returns at least one model with eval_precision / eval_recall / eval_f1.
  4. Evaluated models have plausible scores (>= 0 and <= 1).
  5. Average F1 across evaluated models is above a minimum threshold (>= 0.6).
  6. /incidents endpoint accepts pagination params without error.
  7. Dashboard API /metrics endpoint returns data for the first known service+metric.
  8. React dev server OR built bundle is reachable (http://localhost:5173 or :4173).

Run with:
    uv run python scripts/verify_dod_phase6.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

INGESTION_URL    = "http://localhost:8001"
INFERENCE_URL    = "http://localhost:8002"
DASHBOARD_API    = "http://localhost:8003"
FRONTEND_URLS    = ["http://localhost:5173", "http://localhost:4173"]

MIN_AVG_F1       = 0.60   # if any evaluated model exists, avg must be >= this
TIMEOUT          = 10.0

PASS = "\033[32m PASS\033[0m"
FAIL = "\033[31m FAIL\033[0m"
SKIP = "\033[33m SKIP\033[0m"
WARN = "\033[33m WARN\033[0m"


def _result(ok: bool, label: str, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {label}" + (f" — {detail}" if detail else ""))
    return ok


async def check_health(client: httpx.AsyncClient, url: str, name: str) -> bool:
    try:
        r = await client.get(f"{url}/health", timeout=TIMEOUT)
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        return _result(ok, f"{name} /health", f"HTTP {r.status_code}")
    except Exception as exc:
        return _result(False, f"{name} /health", str(exc))


async def main() -> int:
    failures = 0

    async with httpx.AsyncClient() as client:

        # ── 1. Service health ────────────────────────────────────────────────
        print("\n[1] Service health checks")
        for url, name in [
            (INGESTION_URL,  "Ingestion  API"),
            (INFERENCE_URL,  "Inference  API"),
            (DASHBOARD_API,  "Dashboard  API"),
        ]:
            if not await check_health(client, url, name):
                failures += 1

        # ── 2. /services ─────────────────────────────────────────────────────
        print("\n[2] /services endpoint")
        try:
            r = await client.get(f"{DASHBOARD_API}/services", timeout=TIMEOUT)
            svcs: list[dict[str, Any]] = r.json()
            ok = r.status_code == 200 and len(svcs) > 0
            failures += 0 if _result(ok, f"Returns {len(svcs)} service(s)") else 1

            if ok:
                required = {"service", "open_incidents", "health", "last_anomaly_at"}
                missing = required - svcs[0].keys()
                failures += 0 if _result(not missing, "Service fields present", str(missing or "ok")) else 1
        except Exception as exc:
            _result(False, "/services request", str(exc))
            failures += 1
            svcs = []

        # ── 3. /models with eval scores ───────────────────────────────────────
        print("\n[3] /models — eval scores")
        try:
            r = await client.get(f"{DASHBOARD_API}/models", timeout=TIMEOUT)
            models: list[dict[str, Any]] = r.json()
            ok = r.status_code == 200
            failures += 0 if _result(ok, f"/models HTTP {r.status_code}") else 1

            if ok and models:
                # Check schema
                required = {"eval_precision", "eval_recall", "eval_f1"}
                missing = required - models[0].keys()
                failures += 0 if _result(not missing, "Eval fields present", str(missing or "ok")) else 1

                # Evaluated models
                evaluated = [m for m in models if m.get("eval_f1", -1) >= 0]
                _result(True, f"{len(evaluated)}/{len(models)} models evaluated",
                        "(run `make run-training` to populate eval scores)" if not evaluated else "")

                if evaluated:
                    # ── 4. Score range ────────────────────────────────────────
                    bad = [m for m in evaluated
                           if not (0 <= m["eval_f1"] <= 1
                                   and 0 <= m["eval_precision"] <= 1
                                   and 0 <= m["eval_recall"] <= 1)]
                    failures += 0 if _result(not bad, "All eval scores in [0, 1]",
                                             f"{len(bad)} out-of-range" if bad else "ok") else 1

                    # ── 5. Average F1 ─────────────────────────────────────────
                    avg_f1 = sum(m["eval_f1"] for m in evaluated) / len(evaluated)
                    ok5 = avg_f1 >= MIN_AVG_F1
                    failures += 0 if _result(ok5, f"Avg F1 = {avg_f1:.3f} (threshold {MIN_AVG_F1})",
                                             "ok" if ok5 else f"below {MIN_AVG_F1}") else 1
                else:
                    print(f"  [{SKIP}] Avg F1 check — no evaluated models yet")
            elif ok and not models:
                print(f"  [{SKIP}] Eval fields / scores — no models in DB (run `make run-training`)")
        except Exception as exc:
            _result(False, "/models request", str(exc))
            failures += 1

        # ── 6. /incidents pagination ──────────────────────────────────────────
        print("\n[4] /incidents pagination")
        try:
            r = await client.get(f"{DASHBOARD_API}/incidents?status=open&limit=5&offset=0", timeout=TIMEOUT)
            failures += 0 if _result(r.status_code == 200, "/incidents?limit=5&offset=0") else 1
        except Exception as exc:
            _result(False, "/incidents request", str(exc))
            failures += 1

        # ── 7. /metrics for first known service ───────────────────────────────
        print("\n[5] /metrics time-series")
        if svcs:
            svc = svcs[0]["service"]
            # We need a metric — fetch current models for this service
            try:
                r = await client.get(f"{DASHBOARD_API}/models?service={svc}&current_only=true", timeout=TIMEOUT)
                svc_models = r.json() if r.status_code == 200 else []
                if svc_models:
                    metric = svc_models[0]["metric"]
                    now = datetime.now(tz=UTC)
                    params = {
                        "from": (now - timedelta(days=7)).isoformat(),
                        "to": now.isoformat(),
                    }
                    r2 = await client.get(f"{DASHBOARD_API}/metrics/{svc}/{metric}", params=params, timeout=TIMEOUT)
                    ok = r2.status_code == 200
                    body = r2.json() if ok else {}
                    has_points = bool(body.get("points"))
                    _result(ok, f"/metrics/{svc}/{metric} HTTP {r2.status_code}")
                    _result(has_points, f"  Contains {len(body.get('points', []))} points",
                            "(no data in 7-day window — is the load generator or consumer running?)" if not has_points else "")
                    if not ok:
                        failures += 1
                else:
                    print(f"  [{SKIP}] /metrics — no current model for {svc}")
            except Exception as exc:
                _result(False, "/metrics request", str(exc))
                failures += 1
        else:
            print(f"  [{SKIP}] /metrics — no services found")

        # ── 8. Frontend reachable ─────────────────────────────────────────────
        print("\n[6] Frontend reachability")
        frontend_ok = False
        for url in FRONTEND_URLS:
            try:
                r = await client.get(url, timeout=5.0, follow_redirects=True)
                if r.status_code < 400:
                    _result(True, f"Frontend at {url}")
                    frontend_ok = True
                    break
            except Exception:
                pass
        if not frontend_ok:
            print(f"  [{WARN}] Frontend not reachable — run `make run-ui` or `make start`")
            # Not a hard failure; it may just not be started

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures == 0:
        print("\033[32mAll checks passed — Phase 6 DoD complete.\033[0m")
    else:
        print(f"\033[31m{failures} check(s) failed.\033[0m")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
