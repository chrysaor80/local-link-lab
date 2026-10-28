"""Fail closed if the shell-controlled test receiver leaks into release DEX files."""
from pathlib import Path
from zipfile import ZipFile


def has_control(apk):
    with ZipFile(apk) as archive:
        return any(b"LabControlReceiver" in archive.read(name)
                   for name in archive.namelist() if name.endswith(".dex"))


if __name__ == "__main__":
    debug = Path("app/build/outputs/apk/debug/app-debug.apk")
    release = Path("app/build/outputs/apk/release/app-release-unsigned.apk")
    if not has_control(debug):
        raise SystemExit("Variant guard FAIL: debug control was not compiled")
    if has_control(release):
        raise SystemExit("Variant guard FAIL: test control leaked into release")
    print("Variant guard PASS: lab control exists in debug and is absent from release DEX.")
