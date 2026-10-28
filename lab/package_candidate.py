"""Promote the tested debug APK only after all required CI evidence is present."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .phases import paused_violations, commit_window
from .identity import STAMP, clean_source, validate_stamp, write_build_stamp

APK = Path("app/build/outputs/apk/debug/app-debug.apk")
CASES = ("S01", "S02", "S03_am_kill", "S03_force_stop", "S03_after_pos_commit", "C07_resume")
MUTANTS = {"MUT01": ("S02", "POS_EXTRA_ID"), "MUT02": ("S01", "ACK_WITHOUT_POS"),
           "MUT03": ("S03_am_kill", "SENT_WHILE_PAUSED")}
REPORTS = {
    "core_jvm": ("core/build/test-results/test", 19, "callerDeadlineStillCancelsAndClosesSocket"),
    "controller_jvm": ("app/build/test-results/testDebugUnitTest", 7, "backgroundDuringProbePublishesNothingAndDoesNotDeliver"),
    "android_normal": ("artifacts/m1-android-tests", 4, "uiToRoomToTcpToPosAndBack"),
    "android_recovery": ("app/build/outputs/androidTest-results", 2, "probeDeadlineIsReportedNotLeftAsChecking"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def stamp(root, source):
    """Run after compilation, before emulator verification; never overwrite an earlier stamp."""
    return write_build_stamp(root / STAMP, source, root / APK)


def build_and_stamp(root):
    """The public stamp command always runs Gradle so it cannot label a leftover APK with HEAD."""
    require(not (root / STAMP).exists(), "A build stamp already exists; preserve the old run before starting another")
    source = clean_source(root)
    gradle = str(root / ("gradlew.bat" if os.name == "nt" else "gradlew"))
    subprocess.run([gradle, "--no-daemon", ":app:assembleDebug"], cwd=root, check=True, timeout=600)
    require(clean_source(root) == source, "Source changed while building")
    return stamp(root, source)


def junit_counts(directory, minimum, required_name):
    reports = sorted(directory.rglob("TEST-*.xml"))
    require(reports, f"Missing JUnit group: {directory.name}")
    seen = set()
    for path in reports:
        suite = ET.parse(path).getroot()
        require(suite.tag == "testsuite", "Unsupported JUnit root")
        require(all(int(suite.attrib[key]) == 0 for key in ("failures", "errors", "skipped")), "JUnit failure/error/skip")
        cases = suite.findall("testcase")
        require(len(cases) == int(suite.attrib["tests"]) and cases, "Empty or inconsistent JUnit suite")
        for case in cases:
            require(not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")), "Non-passing JUnit case")
            key = (case.attrib["classname"], case.attrib["name"])
            require(all(key) and key not in seen, "Missing/duplicate JUnit identity")
            seen.add(key)
    require(len(seen) >= minimum and any(name == required_name for _, name in seen), "Required regression tests are missing")
    return len(seen)


def verify_identity(run, source, digest, verdict, *, kind="normal"):
    require(run["source_commit"] == source and run["source_clean"] is True and run["harness_version"] == 2,
            "Execution must use a clean source and the reviewed v2 harness")
    require(run["verdict"] == verdict and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "Unexpected execution verdict or APK hash")
    validate_stamp(run["build_stamp"], source, digest, kind=kind)
    for key in ("apk_identity", "final_apk_identity"):
        identity = run[key]
        require(identity["installed_sha256"] == digest == identity["build_sha256"], "Installed APK identity differs")
        require(identity["package_path"].startswith("/"), "Missing installed APK path")


def verify_phases(record):
    def phase(name):
        found = [o for o in record["observations"] if o["phase"] == name]
        require(found, f"Required fault checkpoint missing: {name}")
        return found[-1]

    events = record["events"]

    def event(name, *, unique=True):
        found = [e for e in events if e["event"] == name]
        require(found and (not unique or len(found) == 1), f"Missing/ambiguous fault event: {name}")
        return found[0]

    def at(item):
        value = datetime.fromisoformat(item["at"])
        require(value.tzinfo is not None, "Fault evidence needs timezone-aware timestamps")
        return value

    def ordered(*items):
        times = [at(item) for item in items]
        require(times == sorted(times), "Fault events/checkpoints are out of order")
        positions = [events.index(item) for item in items if "event" in item]
        require(positions == sorted(set(positions)), "Fault event sequence is out of order")

    required = ["accepted_paused"]
    if record["scenario_id"] in ("S03_am_kill", "S03_force_stop"):
        required.append("restored_pending")
    for name in required:
        o = phase(name)
        require(o["paused_check"] is True and not paused_violations(o["local"], o["pos_rows"], o["submit_count"]),
                "Pause preconditions were not established")
        require(o["local"]["runtime"] == "사용자가 전송을 일시 중지함", "Paused worker checkpoint missing")
    accepted, final = phase("accepted_paused"), phase("final")
    ordered(event("LOCAL_COMMITTED"), accepted, final)
    case = record["scenario_id"]
    if case.startswith("S03_"):
        before = phase("committed_ack_held") if case == "S03_after_pos_commit" else accepted
        restored = phase("restored_ack_held" if case == "S03_after_pos_commit" else "restored_pending")
        dead, launched = event("OLD_PROCESS_TERMINATED"), event("EXPLICIT_RELAUNCH")
        for item in (dead, launched):
            require(re.fullmatch(r"[1-9][0-9]*", item["pid"]) is not None, "Invalid Android PID")
        require(dead["pid"] != launched["pid"], "Relaunch must have a different PID")
        require(dead["method"] == ("kill" if case == "S03_am_kill" else "force-stop"), "Wrong termination method")
        require(str(before["local"]["pid"]) == dead["pid"] and str(restored["local"]["pid"]) == launched["pid"],
                "Checkpoint PID differs from process events")
        ordered(before, dead, launched, restored, final)
    elif case == "S01":
        ordered(accepted, event("REQUEST_BLOCKED_BEFORE_POS_WRITE", unique=False), phase("request_blocked"),
                event("CONNECTION_DELIVERY_RESTORED"), event("RECOVERY_BUDGET_RESTARTED"), final)
        require(record["recovered_by_resume"] is True, "S01 must identify its explicit recovery resume")
    elif case == "S02":
        ordered(accepted, event("POS_COMMITTED"), event("ACK_DROPPED"), event("ACK_RELEASED", unique=False), final)
        require(record["recovered_by_resume"] is False, "S02 must exercise automatic retry")
    elif case == "C07_resume":
        mismatch = event("DESTINATION_MISMATCH_STOPPED")
        require(mismatch["other_submits"] == 0 and mismatch["other_rows"] == [], "Wrong destination received an order")
        ordered(accepted, event("OTHER_DB_BOUND"), mismatch, phase("identity_mismatch"), event("ORIGINAL_DB_RESTORED"), final)
    if record["scenario_id"] == "S03_after_pos_commit":
        for name in ("committed_ack_held", "restored_ack_held"):
            o = phase(name)
            require(o["commit_window"] is True and commit_window(o["local"], o["pos_rows"],
                    record["original_receipts"], o["released_acks"]), "Process-death ACK window was not established")
        ordered(accepted, event("POS_COMMITTED"), phase("committed_ack_held"))
        released = event("ACK_BARRIER_RELEASED")
        ordered(phase("restored_ack_held"), released, final)
        for ack in [e for e in events if e["event"] == "ACK_RELEASED"]:
            ordered(released, ack, final)
        event("ACK_RELEASED", unique=False)


def validate(root, source, jobs):
    require(re.fullmatch(r"[0-9a-f]{40}", source) is not None, "Full source SHA is required")
    for name in ("spec", "pos", "android"):
        require(jobs.get(name, {}).get("result") == "success", f"Required CI job did not pass: {name}")
    before = read_json(root / "artifacts/verification-input.json")
    validate_stamp(before, source, sha256(root / APK))
    counts = {name: junit_counts(root / folder, minimum, required)
              for name, (folder, minimum, required) in REPORTS.items()}

    normal = read_json(root / "artifacts/m2-normal/summary.json")
    verify_identity(normal, source, before["apk_sha256"], "PASS")
    require(normal["build_stamp"] == before, "Normal execution used a different build stamp")
    require(normal["source_commit"] == source and normal["verdict"] == "PASS", "Normal run did not pass this source")
    require(len(normal["required"]) == len(CASES) and set(normal["required"]) == set(CASES), "Normal scenario contract differs")
    results = normal["results"]
    require(len(results) == len(CASES) and {r["scenario_id"] for r in results} == set(CASES), "Missing/duplicate normal case")
    require(all(r["verdict"] == "PASS" and r["violations"] == [] for r in results), "Non-passing normal case")
    for case in CASES:
        record = read_json(root / "artifacts/m2-normal" / case / "result.json")
        require(record["source_commit"] == source and record["scenario_id"] == case and record["harness_version"] == 2
                and record["verdict"] == "PASS" and record["violations"] == [], "Scenario detail differs from summary")
        verify_phases(record)

    mutants = read_json(root / "artifacts/m2-mutations/summary.json")
    require(mutants["source_commit"] == source and mutants["verdict"] == "PASS", "Mutation run did not pass this source")
    results = mutants["results"]
    require(len(results) == len(MUTANTS) and {r["mutation"] for r in results} == set(MUTANTS), "Missing/duplicate mutant")
    for result in results:
        scenario, violation = MUTANTS[result["mutation"]]
        require(result["base_commit"] == source and result["scenario"] == scenario, "Mutation baseline differs")
        require(result["verdict"] == "KILLED" and result["build_exit"] == 0 and result["install_exit"] == 0
                and result["scenario_exit"] == 1, "Mutation failed for a non-verification reason")
        require(result["expected_violation"] == violation and violation in result["violations"], "Wrong mutation violation")
        execution = result["execution_identity"]
        verify_identity(execution, source, result["apk_sha256"], "FAIL", kind="mutation")
        require(execution["build_stamp"]["mutation"] == result["mutation"]
                and execution["build_stamp"]["patch_sha256"] == result["patch_sha256"], "Mutation build stamp has a different patch")
    restored = mutants["restored_normal_apk"]
    require(restored["verdict"] == "PASS" and restored["build_stamp"] == before, "Normal APK restoration was not verified")
    require(restored["identity"]["installed_sha256"] == restored["identity"]["build_sha256"] == before["apk_sha256"],
            "Restored installed APK differs from the normal build")
    return {"junit_pass_counts": counts, "normal_scenarios": len(CASES), "mutations_killed": len(MUTANTS),
            "apk_sha256": before["apk_sha256"]}


def package(root, output, source, jobs, repository, ci):
    require(not output.exists(), "Candidate output already exists")
    verified = validate(root, source, jobs)  # No output directory exists on a failed gate.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="candidate-staging-", dir=output.parent) as temporary:
        payload = Path(temporary) / "payload"
        payload.mkdir()
        shutil.copyfile(root / APK, payload / "local-link-lab-demo.apk")
        for name in ("pos/__init__.py", "pos/server.py", "pos/store.py", "pos/wire.py", "LICENSE"):
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / name, target)
        shutil.copyfile(repository / "docs/DEMO_QUICKSTART.md", payload / "QUICKSTART.md")
        shutil.copyfile(repository / "docs/WINDOWS.md", payload / "WINDOWS.md")
        files = {str(p.relative_to(payload)).replace("\\", "/"): sha256(p)
                 for p in sorted(payload.rglob("*")) if p.is_file()}
        manifest = {"format_version": 1, "kind": "controlled-demo-candidate", "source_commit": source,
                    "build_variant": "debug", "lab_control_included": True,
                    "evidence_level": "Android API 29 emulator / emulator-nat", "physical_device": "NOT_RUN",
                    "independent_review": "See source repository review records; this gate does not grant approval",
                    "ci": ci, "verification": verified, "files": files}
        (payload / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        payload.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stamp", "package"))
    parser.add_argument("--evidence", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("artifacts/demo-candidate"))
    args = parser.parse_args()
    repository = Path.cwd()
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if args.command == "stamp":
        require(args.evidence.resolve() == repository, "Stamp must use this checkout's build output")
        build_and_stamp(repository)
        print("Built the clean source and recorded its APK hash before emulator verification.")
    else:
        jobs = json.loads(os.environ["CI_NEEDS"])
        ci = {key: os.environ.get(env) for key, env in
              (("repository", "GITHUB_REPOSITORY"), ("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"))}
        package(args.evidence, args.out, source, jobs, repository, ci)
        print(f"Demo candidate created: {args.out} (debug / emulator verified)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Candidate BLOCKED: {exc}") from exc
