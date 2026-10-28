import copy
import json
from pathlib import Path
import tempfile
import unittest

from .package_candidate import APK, CASES, MUTANTS, REPORTS, package, sha256, stamp

SOURCE = "a" * 40
JOBS = {name: {"result": "success"} for name in ("spec", "pos", "android")}


class CandidateGateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "candidate"
        (self.root / APK).parent.mkdir(parents=True)
        (self.root / APK).write_bytes(b"test-fixture-apk")
        stamp(self.root, SOURCE)
        for _, (folder, minimum, required) in REPORTS.items():
            path = self.root / folder / "TEST-fixture.xml"
            path.parent.mkdir(parents=True)
            names = [required, *(f"case_{i}" for i in range(minimum - 1))]
            cases = "".join(f'<testcase classname="fixture" name="{name}"/>' for name in names)
            path.write_text(f'<testsuite tests="{minimum}" failures="0" errors="0" skipped="0">{cases}</testsuite>')
        self.normal = self.root / "artifacts/m2-normal/summary.json"
        self.mutants = self.root / "artifacts/m2-mutations/summary.json"
        self.write(self.normal, {**self.identity(), "required": list(CASES), "verdict": "PASS",
                                 "results": [{"scenario_id": case, "verdict": "PASS", "violations": []} for case in CASES]})
        for case in CASES:
            paused = {"phase": "accepted_paused", "paused_check": True, "submit_count": 0, "pos_rows": [],
                      "local": {"user_paused": True, "runtime": "사용자가 전송을 일시 중지함",
                                "rows": [{"status": "PENDING", "receipt_id": None}]}}
            observations = [paused]
            if case in ("S03_am_kill", "S03_force_stop"):
                observations.append({**paused, "phase": "restored_pending"})
            if case == "S03_after_pos_commit":
                for name in ("committed_ack_held", "restored_ack_held"):
                    observations.append({**paused, "phase": name, "commit_window": True, "released_acks": 0,
                                         "pos_rows": [{"request_id": "x", "receipt_id": "r"}]})
            self.write(self.normal.parent / case / "result.json", {"source_commit": SOURCE, "scenario_id": case,
                       "harness_version": 2, "verdict": "PASS", "violations": [],
                       "observations": observations, "original_receipts": {"x": "r"}})
        self.write(self.mutants, {"source_commit": SOURCE, "verdict": "PASS", "results": [
            {"mutation": name, "base_commit": SOURCE, "scenario": scenario, "expected_violation": violation,
             "apk_sha256": "b" * 64, "execution_identity": {**self.identity("b" * 64), "verdict": "FAIL"},
             "violations": [violation], "verdict": "KILLED", "build_exit": 0, "install_exit": 0, "scenario_exit": 1}
            for name, (scenario, violation) in MUTANTS.items()]})
        # Minimal bundle inputs. This fixture tests the gate, not APK or Android behaviour.
        for name in ("pos/__init__.py", "pos/server.py", "pos/store.py", "pos/wire.py", "LICENSE", "docs/DEMO_QUICKSTART.md", "docs/WINDOWS.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def identity(self, digest=None):
        digest = digest or sha256(self.root / APK)
        identity = {"package_path": "/data/app/fixture/base.apk", "installed_sha256": digest, "build_sha256": digest}
        return {"source_commit": SOURCE, "source_clean": True, "harness_version": 2,
                "apk_identity": identity, "final_apk_identity": identity}

    def blocked(self, jobs=JOBS, source=SOURCE):
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            package(self.root, self.output, source, jobs, self.root, {})
        self.assertFalse(self.output.exists(), "a failed gate must not create a candidate")

    def test_passed_evidence_promotes_identical_apk_and_records_scope(self):
        manifest = package(self.root, self.output, SOURCE, JOBS, self.root, {"run_id": "test"})
        self.assertEqual(sha256(self.output / "local-link-lab-demo.apk"), sha256(self.root / APK))
        self.assertEqual(manifest["physical_device"], "NOT_RUN")
        self.assertEqual(manifest["build_variant"], "debug")
        self.assertEqual(manifest["verification"]["normal_scenarios"], 6)
        for name, digest in manifest["files"].items():
            self.assertEqual(sha256(self.output / name), digest)

    def test_failed_skipped_cancelled_or_missing_prerequisite_blocks_output(self):
        for name in JOBS:
            for state in ("failure", "skipped", "cancelled", ""):
                with self.subTest(job=name, state=state):
                    jobs = copy.deepcopy(JOBS)
                    jobs[name]["result"] = state
                    self.blocked(jobs=jobs)
            jobs = copy.deepcopy(JOBS)
            del jobs[name]
            self.blocked(jobs=jobs)

    def test_wrong_source_or_changed_apk_blocks_output(self):
        self.blocked(source="b" * 40)
        (self.root / APK).write_bytes(b"different-apk-after-test")
        self.blocked()

    def test_missing_stamp_blocks_output(self):
        (self.root / "artifacts/verification-input.json").unlink()
        self.blocked()

    def test_missing_normal_or_duplicate_case_blocks_output(self):
        original = json.loads(self.normal.read_text())
        for cases in (original["results"][:-1], [original["results"][0]] * len(CASES)):
            self.write(self.normal, {**original, "results": cases})
            self.blocked()
        self.normal.unlink()
        self.blocked()

    def test_skip_or_failure_in_junit_blocks_even_when_summary_says_pass(self):
        path = self.root / REPORTS["android_recovery"][0] / "TEST-fixture.xml"
        original = path.read_text()
        for tag in ("failure", "error", "skipped"):
            path.write_text(original.replace('/>', f'><{tag}/></testcase>', 1))
            self.blocked()
        path.write_text(original.replace('skipped="0"', 'skipped="1"'))
        self.blocked()
        path.unlink()
        self.blocked()

    def test_mutant_build_failure_wrong_violation_or_wrong_source_blocks(self):
        original = json.loads(self.mutants.read_text())
        for change in ({"build_exit": 1}, {"install_exit": 1}, {"scenario_exit": 124},
                       {"violations": ["UNRELATED_ERROR"]}, {"base_commit": "b" * 40}, {"verdict": "SURVIVED"}):
            altered = copy.deepcopy(original)
            altered["results"][0].update(change)
            self.write(self.mutants, altered)
            self.blocked()

    def test_existing_candidate_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("existing")
        with self.assertRaises(ValueError):
            package(self.root, self.output, SOURCE, JOBS, self.root, {})
        self.assertEqual(sentinel.read_text(), "existing")

    def test_empty_or_inconsistent_junit_cannot_look_successful(self):
        path = self.root / REPORTS["core_jvm"][0] / "TEST-fixture.xml"
        path.write_text('<testsuite tests="19" failures="0" errors="0" skipped="0"/>')
        self.blocked()

    def test_legacy_harness_dirty_source_or_different_installed_apk_blocks(self):
        original = json.loads(self.normal.read_text())
        for change in ({"harness_version": 1}, {"source_clean": False}, {"final_apk_identity": {}},
                       {"apk_identity": {"build_sha256": sha256(self.root / APK), "installed_sha256": "b" * 64}}):
            self.write(self.normal, {**original, **change})
            self.blocked()

    def test_missing_or_false_fault_window_blocks_despite_pass_summary(self):
        path = self.normal.parent / "S03_after_pos_commit/result.json"
        original = json.loads(path.read_text())
        for mode in ("missing", "already_acked", "ack_released"):
            record = copy.deepcopy(original)
            if mode == "missing":
                record["observations"].pop()
            elif mode == "already_acked":
                record["observations"][-1]["local"]["rows"][0]["status"] = "ACKNOWLEDGED"
            else:
                record["observations"][-1]["released_acks"] = 1
            self.write(path, record)
            self.blocked()

    def test_pause_ignored_or_missing_third_mutant_blocks(self):
        path = self.normal.parent / "S03_am_kill/result.json"
        original = json.loads(path.read_text())
        altered = copy.deepcopy(original)
        altered["observations"][-1]["submit_count"] = 1
        self.write(path, altered)
        self.blocked()
        self.write(path, original)
        mutants = json.loads(self.mutants.read_text())
        mutants["results"] = [r for r in mutants["results"] if r["mutation"] != "MUT03"]
        self.write(self.mutants, mutants)
        self.blocked()


if __name__ == "__main__":
    unittest.main()
