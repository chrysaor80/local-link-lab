"""Fail closed if the shell-controlled test receiver leaks into release DEX or manifest."""
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile


def has_control(apk):
    with ZipFile(apk) as archive:
        return any(b"LabControlReceiver" in archive.read(name)
                   for name in archive.namelist() if name.endswith(".dex"))


def manifest(apk):
    tool = shutil.which("aapt2")
    if tool is None:
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if not sdk:
            raise RuntimeError("aapt2 or ANDROID_HOME is required to inspect binary manifests")
        tool = str(Path(sdk) / "build-tools/35.0.0" / ("aapt2.exe" if os.name == "nt" else "aapt2"))
    return subprocess.check_output([tool, "dump", "xmltree", str(apk), "--file", "AndroidManifest.xml"], text=True)


def check_variants(debug, release, manifest_reader=manifest):
    if not has_control(debug):
        raise SystemExit("Variant guard FAIL: debug control was not compiled")
    if has_control(release):
        raise SystemExit("Variant guard FAIL: test control leaked into release")
    if "LabControlReceiver" not in manifest_reader(debug):
        raise SystemExit("Variant guard FAIL: debug manifest has no lab receiver")
    if "LabControlReceiver" in manifest_reader(release):
        raise SystemExit("Variant guard FAIL: test control leaked into release manifest")
    print("Variant guard PASS: lab control exists in debug and is absent from release DEX and manifest.")


if __name__ == "__main__":
    check_variants(Path("app/build/outputs/apk/debug/app-debug.apk"),
                   Path("app/build/outputs/apk/release/app-release-unsigned.apk"))
