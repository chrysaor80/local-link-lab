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
import subprocess
import time
import uuid

from pos.server import PosServer
from pos.store import Store
from .verdict import evaluate, summarize

PACKAGE = "dev.locallinklab.app"
CASES = ("S01", "S02", "S03_am_kill", "S03_force_stop", "S03_after_pos_commit")


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

    async def run(self, *args, timeout=20, check=True):
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
        return text

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
    record = {"scenario_id": scenario, "source_commit": source_sha, "execution_level": "ANDROID_EXTERNAL",
              "network_path": "emulator-nat", "started_at": now(), "verdict": "BLOCKED", "events": [], "violations": []}
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

    def event(name, **details):
        record["events"].append({"event": name, "at": now(), **details})

    async def before_submit(request):
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
        if scenario == "S03_after_pos_commit":
            event("ACK_HELD", request_id=request["request_id"])
            await allow_ack.wait()
        return True

    server = await PosServer(store, before_submit=before_submit, after_commit=after_commit).start()
    last_snapshot = None

    async def observe(label, *, final=False):
        nonlocal last_snapshot
        last_snapshot = await adb.control("snapshot")
        rows = pos_rows(store)
        violations = evaluate(baseline, last_snapshot["rows"], rows, store.db_id,
                              final=final, original_receipts=receipts)
        record["observations"].append({"phase": label, "at": now(), "local": last_snapshot, "pos_rows": rows, "violations": violations})
        return violations

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
        if not admission["rows"] or admission["rows"][0]["status"] != "PENDING":
            raise Blocked("Acceptance did not leave a committed pending order")
        event("LOCAL_COMMITTED", request_id=baseline[0]["request_id"])
        save(folder / "admission.json", admission)

        if scenario in ("S03_am_kill", "S03_force_stop"):
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
            snapshot = await adb.control("snapshot")
            if not snapshot["user_paused"]:
                record["violations"] = ["USER_PAUSE_LOST"]
            record["violations"] += await observe("restored_pending")
        if not record["violations"]:
            await adb.control("resume")
            if scenario == "S01":
                await asyncio.wait_for(blocked_request.wait(), 8)
                record["violations"] += await observe("request_blocked")
                before_blocked = False
                event("CONNECTION_DELIVERY_RESTORED")
            elif scenario == "S02":
                await asyncio.wait_for(committed.wait(), 8)
            elif scenario == "S03_after_pos_commit":
                await asyncio.wait_for(committed.wait(), 8)
                record["violations"] += await observe("committed_ack_held")
                old = await adb.pid()
                if not old:
                    raise Blocked("Missing original PID")
                await adb.run("shell", "am", "force-stop", PACKAGE)
                await adb.wait_dead(old)
                event("OLD_PROCESS_TERMINATED", pid=old, method="force-stop")
                allow_ack.set()
                await adb.launch()
                new = await adb.pid()
                if not new or new == old:
                    raise Blocked("No new Android PID after explicit relaunch")
                event("EXPLICIT_RELAUNCH", pid=new)

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
    sha = args.source_commit or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    adb = Adb(args.serial)
    results = []
    for scenario in args.scenario or CASES:
        results.append(await run_case(adb, scenario, out / scenario, sha))
    required = args.scenario or list(CASES)
    verdict = summarize(results, required)
    save(out / "summary.json", {"source_commit": sha, "required": required, "verdict": verdict,
                                "results": [{key: r[key] for key in ("scenario_id", "verdict", "violations")} for r in results]})
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--scenario", action="append", choices=CASES)
    parser.add_argument("--source-commit", help="Base revision when executing an isolated mutation copy")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
