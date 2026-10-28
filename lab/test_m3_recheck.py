"""Candidate-gate regressions written by the reviewer against 70a6347 (M2 fix re-check).

Reuses the CandidateGateTest fixture without re-running its tests.
"""
import json
import copy
import unittest

from . import test_candidate as base

PROCESS_EVENTS = ("OLD_PROCESS_TERMINATED", "EXPLICIT_RELAUNCH")


class ProcessDeathEvidenceGateTest(unittest.TestCase):
    setUp = base.CandidateGateTest.setUp
    write = base.CandidateGateTest.write
    identity = base.CandidateGateTest.identity
    blocked = base.CandidateGateTest.blocked

    def test_fixture_is_otherwise_promotable(self):
        """Control: the updated fixture includes the required fault events."""
        base.package(self.root, self.root / "control-candidate", base.SOURCE, base.JOBS, self.root, {})

    def test_s03_without_observed_pid_death_and_relaunch_is_blocked(self):
        """Expected FAIL at 70a6347: verify_phases re-checks S03 phase observations but never the
        OLD_PROCESS_TERMINATED / EXPLICIT_RELAUNCH events (old PID gone, new PID different), so an S03
        record without any observed process death is still promoted to a demo candidate."""
        for case in ("S03_am_kill", "S03_force_stop", "S03_after_pos_commit"):
            path = self.normal.parent / case / "result.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            record = copy.deepcopy(original)
            record["events"] = [e for e in record["events"] if e["event"] not in PROCESS_EVENTS]
            self.write(path, record)
            with self.subTest(case=case):
                self.blocked()
            self.write(path, original)

    def test_invalid_pid_order_method_or_checkpoint_identity_is_blocked(self):
        path = self.normal.parent / "S03_force_stop/result.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for mode in ("same_pid", "empty_pid", "late_death", "reversed_events", "wrong_method", "wrong_snapshot_pid"):
            record = copy.deepcopy(original)
            dead, launched = record["events"][1:3]
            if mode == "same_pid": launched["pid"] = dead["pid"]
            elif mode == "empty_pid": dead["pid"] = ""
            elif mode == "late_death": dead["at"] = "2026-10-28T00:00:08+00:00"
            elif mode == "reversed_events": record["events"][1:3] = [launched, dead]
            elif mode == "wrong_method": dead["method"] = "kill"
            else: record["observations"][1]["local"]["pid"] = 333
            self.write(path, record)
            with self.subTest(mode=mode): self.blocked()

    def test_missing_fault_events_or_wrong_destination_effect_blocks(self):
        for case, name in (("S01", "REQUEST_BLOCKED_BEFORE_POS_WRITE"), ("S02", "ACK_DROPPED"),
                           ("C07_resume", "DESTINATION_MISMATCH_STOPPED")):
            path = self.normal.parent / case / "result.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            record = copy.deepcopy(original)
            record["events"] = [e for e in record["events"] if e["event"] != name]
            self.write(path, record)
            with self.subTest(case=case): self.blocked()
            self.write(path, original)
        path = self.normal.parent / "C07_resume/result.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for change in ({"other_submits": 1}, {"other_rows": [{"request_id": "wrong-db"}]}):
            record = copy.deepcopy(original)
            next(e for e in record["events"] if e["event"] == "DESTINATION_MISMATCH_STOPPED").update(change)
            self.write(path, record)
            with self.subTest(change=change): self.blocked()

    def test_ack_release_before_relaunch_or_missing_resume_classification_blocks(self):
        path = self.normal.parent / "S03_after_pos_commit/result.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        record = copy.deepcopy(original)
        next(e for e in record["events"] if e["event"] == "ACK_RELEASED")["at"] = "2026-10-28T00:00:03+00:00"
        self.write(path, record)
        self.blocked()
        self.write(path, original)
        path = self.normal.parent / "S01/result.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["recovered_by_resume"] = False
        self.write(path, record)
        self.blocked()


if __name__ == "__main__":
    unittest.main()
