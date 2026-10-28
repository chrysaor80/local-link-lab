"""Run real Android fault cases from outside the app, on a disposable emulator.

python -m lab.android_run --out artifacts/m2
The installed APK must be this project's debug variant. No production control endpoint exists.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
import uuid

from pos.server import PosServer
from pos.store import Store
from .verdict import evaluate, summarize
from .identity import APK, STAMP, clean_source, installed_apk, check_stamp
from .phases import paused_violations, commit_window

PACKAGE = "dev.locallinklab.app"
CASES = ("S01", "S02", "S03_am_kill", "S03_force_stop", "S03_after_pos_commit", "C07_resume")


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class Blocked(RuntimeError):
    pass


class Adb:
    def __init__(self, serial):
        self.serial = serial
        self.history = []

    async def run(self, *args, timeout=20, check=True, binary=False):
        self.history.append({"at": now(), "command": ["adb", *args]})
        proc = await asyncio.create_subprocess_exec("adb", "-s", self.serial, *args,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill(); await proc.wait()
            raise Blocked(f"adb deadline: {args[:3]}")
        text = out.decode("utf-8", errors="replace").strip()
        if check and proc.returncode:
            raise Blocked(f"adb failed ({proc.returncode}): {args[:3]}: {err.decode(errors='replace')}")
        return out if binary else text

    async def control(self, command, **values):
        token = str(uuid.uuid4())
        args = ["shell", "am", "broadcast", "-n", f"{PACKAGE}/.LabControlReceiver",
                "--es", "token", token, "--es", "command", command]
        for key, value in values.items():
            args += ["--es", key, str(value)]
        response = await self.run(*args)
        if "Permission Denial" in response or "SecurityException" in response:
            raise Blocked(response)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            raw = await self.run("exec-out", "run-as", PACKAGE, "cat", f"files/lab-{token}.json", check=False)
            try:
                result = json.loads(raw)
            except (ValueError, TypeError):
                await asyncio.sleep(0.1)  # Poll observable completion, never guess a commit time.
                continue
            if result.get("token") != token or not result.get("ok"):
                raise Blocked(f"Debug command did not complete: {result}")
            await self.run("shell", "run-as", PACKAGE, "rm", f"files/lab-{token}.json")
            return result
        raise Blocked(f"No completed debug command: {command}; last response: {raw[:150]}")

    async def launch(self):
        await self.run("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")

    async def pid(self):
        return await self.run("shell", "pidof", PACKAGE, check=False)

    async def wait_dead(self, old):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = await self.pid()
            if not current:
                return
            if current != old:
                raise Blocked("Unexpected automatic process restart")
            await asyncio.sleep(0.1)
        raise Blocked("Old Android PID did not terminate")


def pos_rows(store):
    with closing(store.connect()) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM orders ORDER BY request_id")]


async def run_case(adb, scenario, folder, source_sha):
    folder.mkdir(parents=True, exist_ok=False)
    record = {"scenario_id": scenario, "source_commit": source_sha, "harness_version": 2, "execution_level": "ANDROID_EXTERNAL",
              "network_path": "emulator-nat", "started_at": now(), "verdict": "BLOCKED", "events": [], "violations": [],
              "recovered_by_resume": False}
    commands_start = len(adb.history)
    store = Store(folder / "pos.db")
    baseline = [dict(request_id=str(uuid.uuid4()), pos_db_id=store.db_id,
                     item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000)]
    # The baseline is written BEFORE the app accepts the order and never populated from its database.
    save(folder / "baseline.json", baseline)
    receipts = {}
    blocked_request = asyncio.Event()
    committed = asyncio.Event()
    allow_ack = asyncio.Event()
    before_blocked = scenario == "S01"
    first_drop = True
    other_store = Store(folder / "other-pos.db") if scenario == "C07_resume" else None
    other_submits = 0
    submit_count = 0
    released_acks = 0

    def event(name, **details):
        record["events"].append({"event": name, "at": now(), **details})

    async def before_submit(request):
        nonlocal other_submits, submit_count
        submit_count += 1
        event("SUBMIT_RECEIVED", request_id=request["request_id"], count=submit_count)
        if other_store is not None and server.store is other_store:
            other_submits += 1
        if before_blocked:
            event("REQUEST_BLOCKED_BEFORE_POS_WRITE", request_id=request["request_id"])
            blocked_request.set()
            return False
        return True

    async def after_commit(request, response):
        nonlocal first_drop
        receipts[request["request_id"]] = response["receipt_id"]
        event("POS_COMMITTED", request_id=request["request_id"], receipt_id=response["receipt_id"])
        committed.set()
        if scenario == "S02" and first_drop:
            first_drop = False
            event("ACK_DROPPED", request_id=request["request_id"])
            return False
        return True

    async def before_ack(request, response):
        nonlocal released_acks
        if scenario == "S03_after_pos_commit":
            event("ACK_HELD", request_id=request["request_id"])
            await allow_ack.wait()
        released_acks += 1
        event("ACK_RELEASED", request_id=request["request_id"])
        return True

    server = await PosServer(store, before_submit=before_submit, after_commit=after_commit, before_ack=before_ack).start()
    last_snapshot = None

    async def observe(label, *, final=False, paused=False, require_window=False):
        nonlocal last_snapshot
        last_snapshot = await adb.control("snapshot")
        rows = pos_rows(store)
        violations = evaluate(baseline, last_snapshot["rows"], rows, store.db_id,
                              final=final, original_receipts=receipts)
        if paused:
            violations += paused_violations(last_snapshot, rows, submit_count)
        window = commit_window(last_snapshot, rows, receipts, released_acks) if require_window else None
        record["observations"].append({"phase": label, "at": now(), "local": last_snapshot, "pos_rows": rows,
                                       "submit_count": submit_count, "released_acks": released_acks,
                                       "final": final, "paused_check": paused, "commit_window": window,
                                       "violations": sorted(set(violations))})
        if require_window and not window:
            raise Blocked("Fault window missed: expected PENDING, one committed POS row and every ACK held")
        return violations

    async def observe_paused(label):
        # Observe worker readiness as well as persisted settings. A flag alone proves no behaviour.
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            violations = await observe(label, paused=True)
            if violations or last_snapshot["runtime"] == "사용자가 전송을 일시 중지함":
                return violations
            await asyncio.sleep(0.1)
        raise Blocked("Paused foreground worker did not reach an observable checkpoint")

    record["observations"] = []
    try:
        if await adb.run("shell", "getprop", "ro.kernel.qemu") != "1":
            raise Blocked("Automatic data reset is restricted to disposable Android emulators")
        record["android_api"] = await adb.run("shell", "getprop", "ro.build.version.sdk")
        record["android_model"] = await adb.run("shell", "getprop", "ro.product.model")
        cleared = await adb.run("shell", "pm", "clear", PACKAGE)
        if "Success" not in cleared:
            raise Blocked(f"Could not reset test app: {cleared}")
        await adb.launch()
        await adb.control("configure", host="10.0.2.2", port=server.port)
        await adb.control("pause")
        admission = await adb.control("accept", request_id=baseline[0]["request_id"])
        if not admission["rows"]:
            raise Blocked("Acceptance did not leave a committed order")
        event("LOCAL_COMMITTED", request_id=baseline[0]["request_id"])
        save(folder / "admission.json", admission)
        record["violations"] += await observe_paused("accepted_paused")

        if not record["violations"] and scenario in ("S03_am_kill", "S03_force_stop"):
            if scenario == "S03_am_kill":
                await adb.run("shell", "input", "keyevent", "KEYCODE_HOME")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    snap = await adb.control("snapshot")
                    if snap["runtime"] == "백그라운드 · 전송 중지":
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise Blocked("App did not reach stopped foreground worker state")
            old = await adb.pid()
            if not old:
                raise Blocked("Missing original PID")
            method = "kill" if scenario == "S03_am_kill" else "force-stop"
            await adb.run("shell", "am", method, PACKAGE)
            await adb.wait_dead(old)
            event("OLD_PROCESS_TERMINATED", pid=old, method=method)
            await adb.launch()
            new = await adb.pid()
            if not new or new == old:
                raise Blocked("No new Android PID after explicit relaunch")
            event("EXPLICIT_RELAUNCH", pid=new)
            record["violations"] += await observe_paused("restored_pending")
        if not record["violations"]:
            if scenario == "C07_resume":
                server.store = other_store
                event("OTHER_DB_BOUND", pos_db_id=other_store.db_id)
            await adb.control("resume")
            if scenario == "C07_resume":
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    snapshot = await adb.control("snapshot")
                    if snapshot["runtime"] == "POS DB가 달라 전송을 중지했습니다. 연결 주소를 다시 확인하세요.":
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise Blocked("No observed destination verification stop")
                if other_submits or pos_rows(other_store):
                    record["violations"].append("SUBMITTED_BEFORE_DESTINATION_VERIFIED")
                event("DESTINATION_MISMATCH_STOPPED", other_submits=other_submits, other_rows=pos_rows(other_store))
                record["violations"] += await observe("identity_mismatch")
                server.store = store
                event("ORIGINAL_DB_RESTORED")
                await adb.control("resume")
            elif scenario == "S01":
                await asyncio.wait_for(blocked_request.wait(), 8)
                record["violations"] += await observe("request_blocked")
                before_blocked = False
                event("CONNECTION_DELIVERY_RESTORED")
                # Observation latency must not consume the recovery attempt budget.
                # Explicit recovery also works if a slow ADB host exhausted the old worker.
                await adb.control("resume")
                record["recovered_by_resume"] = True
                event("RECOVERY_BUDGET_RESTARTED")
            elif scenario == "S02":
                await asyncio.wait_for(committed.wait(), 8)
            elif scenario == "S03_after_pos_commit":
                await asyncio.wait_for(committed.wait(), 8)
                record["violations"] += await observe("committed_ack_held", require_window=True)
                old = await adb.pid()
                if not old:
                    raise Blocked("Missing original PID")
                await adb.run("shell", "am", "force-stop", PACKAGE)
                await adb.wait_dead(old)
                event("OLD_PROCESS_TERMINATED", pid=old, method="force-stop")
                await adb.launch()
                new = await adb.pid()
                if not new or new == old:
                    raise Blocked("No new Android PID after explicit relaunch")
                event("EXPLICIT_RELAUNCH", pid=new)
                record["violations"] += await observe("restored_ack_held", require_window=True)
                allow_ack.set()
                event("ACK_BARRIER_RELEASED")

        deadline = time.monotonic() + 35
        while not record["violations"] and time.monotonic() < deadline:
            record["violations"] += await observe("recovery")
            if record["violations"]:
                break
            if last_snapshot["rows"] and all(row["status"] == "ACKNOWLEDGED" for row in last_snapshot["rows"]):
                break
            await asyncio.sleep(0.15)
        record["violations"] += await observe("final", final=True)
        record["violations"] = sorted(set(record["violations"]))
        record["verdict"] = "FAIL" if record["violations"] else "PASS"
    except (Blocked, asyncio.TimeoutError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["verdict"] = "BLOCKED"
    except Exception as exc:
        record["error"] = f"Harness error: {type(exc).__name__}: {exc}"
        record["verdict"] = "BLOCKED"
    finally:
        allow_ack.set()
        await server.close()
        record["final_pos_rows"] = pos_rows(store)
        record["original_receipts"] = receipts
        record["commands"] = adb.history[commands_start:]
        record["finished_at"] = now()
        save(folder / "result.json", record)
    print(json.dumps({key: record[key] for key in ("scenario_id", "verdict", "violations")}), flush=True)
    if "error" in record:
        print(record["error"], flush=True)
    return record


async def main(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    adb = Adb(args.serial)
    try:
        sha = clean_source()
        if args.source_commit and args.source_commit != sha:
            raise ValueError("Mutation base differs from the harness checkout")
        kind = "mutation" if args.source_commit else "normal"
        build_stamp = check_stamp(args.stamp, sha, args.apk, kind=kind)
        identity = await installed_apk(adb, args.apk)
    except (ValueError, OSError, Blocked) as exc:
        save(out / "summary.json", {"verdict": "BLOCKED", "error": str(exc), "results": []})
        print(f"Identity BLOCKED: {exc}", flush=True)
        return 2
    results = []
    for scenario in args.scenario or CASES:
        results.append(await run_case(adb, scenario, out / scenario, sha))
    required = args.scenario or list(CASES)
    verdict = summarize(results, required)
    try:
        final_identity = await installed_apk(adb, args.apk)
        if check_stamp(args.stamp, sha, args.apk, kind=kind) != build_stamp:
            raise ValueError("Build stamp changed during verification")
        if clean_source() != sha:
            raise ValueError("Source changed during verification")
    except (ValueError, OSError, Blocked) as exc:
        final_identity = {"error": str(exc)}
        verdict = "BLOCKED"
    save(out / "summary.json", {"source_commit": sha, "source_clean": True, "harness_version": 2,
                                "build_stamp": build_stamp,
                                "apk_identity": identity, "final_apk_identity": final_identity,
                                "required": required, "verdict": verdict,
                                "results": [{key: r[key] for key in ("scenario_id", "verdict", "violations")} for r in results]})
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--scenario", action="append", choices=CASES)
    parser.add_argument("--source-commit", help="Base revision when executing an isolated mutation copy")
    parser.add_argument("--apk", type=Path, default=APK, help="Expected installed build artifact (normal or isolated mutant)")
    parser.add_argument("--stamp", type=Path, default=STAMP, help="Record created immediately after a successful build")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
