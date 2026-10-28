"""The release guard must still reject bad APK contents under python -O."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).with_name("check_variants.py")


class VariantGuardTest(unittest.TestCase):
    def test_normal_missing_debug_and_release_leak_under_both_modes(self):
        with tempfile.TemporaryDirectory() as work:
            for debug_control, release_control, expected_ok in [(True, False, True), (False, False, False), (True, True, False)]:
                for variant, controlled in [("debug", debug_control), ("release", release_control)]:
                    directory = Path(work) / "app/build/outputs/apk" / variant
                    directory.mkdir(parents=True, exist_ok=True)
                    name = "app-debug.apk" if variant == "debug" else "app-release-unsigned.apk"
                    with ZipFile(directory / name, "w") as archive:
                        archive.writestr("classes.dex", b"LabControlReceiver" if controlled else b"OtherClass")
                for flags in ([], ["-O"]):
                    with self.subTest(debug=debug_control, release=release_control, flags=flags):
                        result = subprocess.run([sys.executable, *flags, str(SCRIPT)], cwd=work, capture_output=True, timeout=10)
                        self.assertEqual(result.returncode == 0, expected_ok, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
