"""The release guard must still reject bad APK contents under python -O."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).with_name("check_variants.py")


class VariantGuardTest(unittest.TestCase):
    def test_normal_missing_debug_and_release_leak_under_both_modes(self):
        with tempfile.TemporaryDirectory() as work:
            # Decoded manifest fixtures are injected; real binary APK decoding runs in Android CI.
            for debug_control, release_control, debug_manifest, release_manifest, expected_ok in [
                (True, False, True, False, True), (False, False, True, False, False),
                (True, True, True, False, False), (True, False, False, False, False),
                (True, False, True, True, False)]:
                for variant, controlled in [("debug", debug_control), ("release", release_control)]:
                    directory = Path(work) / "app/build/outputs/apk" / variant
                    directory.mkdir(parents=True, exist_ok=True)
                    name = "app-debug.apk" if variant == "debug" else "app-release-unsigned.apk"
                    with ZipFile(directory / name, "w") as archive:
                        archive.writestr("classes.dex", b"LabControlReceiver" if controlled else b"OtherClass")
                for flags in ([], ["-O"]):
                    with self.subTest(debug=debug_control, release=release_control, flags=flags):
                        code = ("from pathlib import Path; from lab.check_variants import check_variants; "
                                "debug=Path('app/build/outputs/apk/debug/app-debug.apk'); "
                                "release=Path('app/build/outputs/apk/release/app-release-unsigned.apk'); "
                                f"check_variants(debug, release, lambda p: 'LabControlReceiver' if "
                                f"({debug_manifest!r} if p == debug else {release_manifest!r}) else 'manifest')")
                        env = {**os.environ, "PYTHONPATH": str(SCRIPT.parent.parent)}
                        result = subprocess.run([sys.executable, *flags, "-c", code], cwd=work, env=env, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode == 0, expected_ok, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
