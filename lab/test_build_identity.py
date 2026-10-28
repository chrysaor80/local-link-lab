"""R-02: stale ignored APKs and failed restoration must not become execution evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from .android_run import main as android_main
from .identity import APK, STAMP, check_stamp, clean_source, installed_apk, write_build_stamp
from .mutations import restore_normal
from .package_candidate import build_and_stamp

SOURCE = "a" * 40


class FakeAdb:
    def __init__(self, content):
        self.content, self.history = content, []

    async def run(self, *args, **kwargs):
        self.history.append(list(args))
        if args[0] == "install": return "Success"
        return self.content if kwargs.get("binary") else "package:/data/app/fixture/base.apk"


class BuildIdentityTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.apk = self.root / APK
        self.apk.parent.mkdir(parents=True)
        self.apk.write_bytes(b"normal-apk")
        self.stamp = self.root / STAMP

    async def test_clean_head_and_installed_equality_do_not_allow_stale_ignored_apk(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        git("init")
        (self.root / ".gitignore").write_text("**/build/\nartifacts/\n")
        source = self.root / "source.txt"
        source.write_text("approved")
        git("add", ".gitignore", "source.txt")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
        sha = clean_source(self.root)
        write_build_stamp(self.stamp, sha, self.apk)
        source.write_text("mutated")
        self.apk.write_bytes(b"leftover-mutant-build")
        git("checkout", "--", "source.txt")
        self.assertEqual(clean_source(self.root), sha)
        self.assertEqual((await installed_apk(FakeAdb(self.apk.read_bytes()), self.apk))["installed_sha256"],
                         hashlib.sha256(self.apk.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "Build stamp differs"):
            check_stamp(self.stamp, sha, self.apk)

    async def test_missing_stamp_blocks_android_run_before_any_device_action(self):
        args = SimpleNamespace(out=str(self.root / "out"), serial="unused", source_commit=None,
                               stamp=self.stamp, apk=self.apk, scenario=["S01"])
        with patch("lab.android_run.clean_source", return_value=SOURCE), patch("lab.android_run.installed_apk", new_callable=AsyncMock) as installed:
            self.assertEqual(await android_main(args), 2)
            installed.assert_not_awaited()
        self.assertEqual(json.loads((self.root / "out/summary.json").read_text())["verdict"], "BLOCKED")

    async def test_mutation_stamp_requires_correct_source_apk_and_kind(self):
        write_build_stamp(self.stamp, SOURCE, self.apk, mutation="MUT03", patch_sha256="c" * 64)
        self.assertEqual(check_stamp(self.stamp, SOURCE, self.apk, kind="mutation")["mutation"], "MUT03")
        with self.assertRaises(ValueError): check_stamp(self.stamp, SOURCE, self.apk)
        with self.assertRaises(ValueError): check_stamp(self.stamp, "b" * 40, self.apk, kind="mutation")
        self.apk.write_bytes(b"changed-build")
        with self.assertRaises(ValueError): check_stamp(self.stamp, SOURCE, self.apk, kind="mutation")

    async def test_successful_install_command_is_not_enough_to_verify_restoration(self):
        write_build_stamp(self.stamp, SOURCE, self.apk)
        with patch("lab.mutations.clean_source", return_value=SOURCE):
            wrong = await restore_normal(FakeAdb(b"mutant-still-installed"), self.apk, SOURCE, self.stamp)
            correct = await restore_normal(FakeAdb(self.apk.read_bytes()), self.apk, SOURCE, self.stamp)
        self.assertEqual(wrong["verdict"], "BLOCKED")
        self.assertEqual(correct["verdict"], "PASS")
        self.assertEqual(correct["identity"]["installed_sha256"], correct["build_stamp"]["apk_sha256"])

    async def test_public_stamp_command_builds_first_and_never_stamps_failed_build(self):
        self.apk.write_bytes(b"stale")
        with patch("lab.package_candidate.clean_source", return_value=SOURCE), patch("lab.package_candidate.subprocess.run", side_effect=lambda *a, **k: self.apk.write_bytes(b"rebuilt")) as build:
            value = build_and_stamp(self.root)
        self.assertIn(":app:assembleDebug", build.call_args.args[0])
        self.assertEqual(value["apk_sha256"], hashlib.sha256(b"rebuilt").hexdigest())
        self.stamp.unlink()
        with patch("lab.package_candidate.clean_source", return_value=SOURCE), patch("lab.package_candidate.subprocess.run", side_effect=subprocess.CalledProcessError(1, "gradle")):
            with self.assertRaises(subprocess.CalledProcessError): build_and_stamp(self.root)
        self.assertFalse(self.stamp.exists())


if __name__ == "__main__":
    unittest.main()
