"""Assert that the shell-controlled test receiver is absent from release DEX files."""
from pathlib import Path
from zipfile import ZipFile


def has_control(apk):
    with ZipFile(apk) as archive:
        return any(b"LabControlReceiver" in archive.read(name)
                   for name in archive.namelist() if name.endswith(".dex"))


if __name__ == "__main__":
    debug = Path("app/build/outputs/apk/debug/app-debug.apk")
    release = Path("app/build/outputs/apk/release/app-release-unsigned.apk")
    assert has_control(debug), "Debug control was not compiled"
    assert not has_control(release), "Test control leaked into release"
    print("Variant guard PASS: lab control exists in debug and is absent from release DEX.")
