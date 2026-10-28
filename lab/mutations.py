"""Build isolated defective copies; only matching data-invariant failures count as kills."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .android_run import CASES

ENGINE = Path("core/src/main/kotlin/dev/locallinklab/core/DeliveryEngine.kt")
MUTANTS = {
    "MUT01": {"scenario": "S02", "expected": "POS_EXTRA_ID"},
    "MUT02": {"scenario": "S01", "expected": "ACK_WITHOUT_POS"},
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("Mutation target changed; review the patch instead of guessing")
    return text.replace(old, new, 1)


def mutate(text, name):
    if name == "MUT01":
        text = replace_once(text, "val pending = outbox.nextPending()", "var pending = outbox.nextPending()")
        return replace_once(text, '                event("전송 중 (${attempt + 1}/$attempts)")',
                            '                if (attempt > 0) pending = pending.copy(requestId = java.util.UUID.randomUUID().toString())\n'
                            '                event("전송 중 (${attempt + 1}/$attempts)")')
    if name == "MUT02":
        return replace_once(text, "                    when (val response = transport.exchange(endpoint, Message.Submit(pending))) {",
                            "                    outbox.acknowledge(pending.requestId, java.util.UUID.randomUUID().toString())\n"
                            "                    when (val response = transport.exchange(endpoint, Message.Submit(pending))) {")
    raise ValueError(name)


def run_logged(argv, *, cwd, log, timeout):
    with log.open("w", encoding="utf-8") as output:
        try:
            return subprocess.run(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            output.write("\nHARNESS DEADLINE: not a mutation kill\n")
            return 124


def main(args):
    root = Path.cwd()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    baseline = json.loads(Path(args.normal_summary).read_text(encoding="utf-8"))
    if baseline["source_commit"] != sha or baseline["verdict"] != "PASS" or set(baseline["required"]) != set(CASES):
        raise RuntimeError("The same base revision must pass every normal fault case first")
    if subprocess.check_output(["adb", "-s", args.serial, "shell", "getprop", "ro.kernel.qemu"], text=True).strip() != "1":
        raise RuntimeError("Mutation APK installation is restricted to disposable emulators")
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=False)
    outcomes = []
    normal_apk = root / "app/build/outputs/apk/debug/app-debug.apk"
    try:
        for name, config in MUTANTS.items():
            folder = output / name
            folder.mkdir()
            outcome = {"mutation": name, "base_commit": sha, "scenario": config["scenario"],
                       "expected_violation": config["expected"], "verdict": "BLOCKED"}
            with tempfile.TemporaryDirectory(prefix="local-link-mutant-") as temp:
                target = Path(temp) / "repo"
                shutil.copytree(root, target, ignore=shutil.ignore_patterns(
                    ".git", ".gradle", ".kotlin", "build", "artifacts", "local.properties", ".idea", ".venv", "__pycache__"))
                original = (target / ENGINE).read_text(encoding="utf-8")
                changed = mutate(original, name)
                (target / ENGINE).write_text(changed, encoding="utf-8")
                patch = "".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile=str(ENGINE), tofile=str(ENGINE)))
                (folder / "mutation.diff").write_text(patch, encoding="utf-8")
                outcome["patch_sha256"] = hashlib.sha256(patch.encode()).hexdigest()
                gradle = str(target / ("gradlew.bat" if os.name == "nt" else "gradlew"))
                build_code = run_logged([gradle, "--no-daemon", ":app:assembleDebug"], cwd=target, log=folder / "build.log", timeout=300)
                outcome["build_exit"] = build_code
                if build_code == 0:
                    apk = target / "app/build/outputs/apk/debug/app-debug.apk"
                    outcome["apk_sha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()
                    install = run_logged(["adb", "-s", args.serial, "install", "-r", str(apk)], cwd=root, log=folder / "install.log", timeout=60)
                    outcome["install_exit"] = install
                    if install == 0:
                        # Run the ORIGINAL harness and verdict, not a copy altered by the mutation.
                        code = run_logged([sys.executable, "-m", "lab.android_run", "--out", str(folder / "execution"),
                                           "--serial", args.serial, "--scenario", config["scenario"], "--source-commit", sha],
                                          cwd=root, log=folder / "run.log", timeout=120)
                        outcome["scenario_exit"] = code
                        report = folder / "execution" / config["scenario"] / "result.json"
                        if report.exists():
                            result = json.loads(report.read_text(encoding="utf-8"))
                            outcome["violations"] = result["violations"]
                            if code == 1 and result["verdict"] == "FAIL" and config["expected"] in result["violations"]:
                                outcome["verdict"] = "KILLED"
                            elif code == 0 and result["verdict"] == "PASS":
                                outcome["verdict"] = "SURVIVED"
                outcomes.append(outcome)
                (folder / "result.json").write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(outcome), flush=True)
    finally:
        subprocess.run(["adb", "-s", args.serial, "install", "-r", str(normal_apk)], check=True, timeout=60)
    passed = len(outcomes) == len(MUTANTS) and all(r["verdict"] == "KILLED" for r in outcomes)
    (output / "summary.json").write_text(json.dumps({"source_commit": sha, "verdict": "PASS" if passed else "FAIL", "results": outcomes}, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-summary", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    raise SystemExit(main(parser.parse_args()))
