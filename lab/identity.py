"""Bind observations to a clean checkout and the bytes actually installed by ADB."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

PACKAGE = "dev.locallinklab.app"
APK = Path("app/build/outputs/apk/debug/app-debug.apk")
STAMP = Path("artifacts/verification-input.json")


def validate_stamp(value, source, digest, *, kind="normal"):
    if not isinstance(value, dict):
        raise ValueError("Build stamp must be an object")
    if (value.get("format_version") != 1 or value.get("source_commit") != source
            or value.get("apk_sha256") != digest or value.get("kind") != kind
            or re.fullmatch(r"[0-9a-f]{40}", source) is None
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
        raise ValueError("Build stamp differs from the source, APK or execution kind; rebuild and stamp first")
    if kind == "mutation" and (not isinstance(value.get("mutation"), str) or not value["mutation"]
                               or not isinstance(value.get("patch_sha256"), str)
                               or re.fullmatch(r"[0-9a-f]{64}", value["patch_sha256"]) is None):
        raise ValueError("Mutation stamp must identify its source patch")
    return value


def check_stamp(path, source, apk, *, kind="normal"):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_stamp(value, source, hashlib.sha256(Path(apk).read_bytes()).hexdigest(), kind=kind)


def write_build_stamp(path, source, apk, *, mutation=None, patch_sha256=None):
    value = {"format_version": 1, "source_commit": source, "apk_sha256": hashlib.sha256(Path(apk).read_bytes()).hexdigest(),
             "kind": "mutation" if mutation else "normal"}
    if mutation:
        value.update(mutation=mutation, patch_sha256=patch_sha256)
    validate_stamp(value, source, value["apk_sha256"], kind=value["kind"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2)
        output.write("\n")
    return value


def clean_source(root=None):
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True).strip():
        raise ValueError("Working tree is dirty; commit the reviewed inputs before recording evidence")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


async def installed_apk(adb, expected):
    expected_hash = hashlib.sha256(Path(expected).read_bytes()).hexdigest()
    paths = (await adb.run("shell", "pm", "path", PACKAGE)).splitlines()
    if len(paths) != 1 or not paths[0].startswith("package:/"):
        raise ValueError("Expected one installed base APK for the demo package")
    path = paths[0].removeprefix("package:")
    digest = hashlib.sha256(await adb.run("exec-out", "cat", path, binary=True)).hexdigest()
    if digest != expected_hash:
        raise ValueError("Installed APK differs from the expected build artifact")
    return {"package_path": path, "installed_sha256": digest, "build_sha256": expected_hash}
