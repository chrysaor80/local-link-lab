"""Bind observations to a clean checkout and the bytes actually installed by ADB."""
import hashlib
from pathlib import Path
import subprocess

PACKAGE = "dev.locallinklab.app"
APK = Path("app/build/outputs/apk/debug/app-debug.apk")


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
