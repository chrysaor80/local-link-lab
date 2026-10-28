import copy
import unittest

from .verdict import evaluate, summarize


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.baseline = [dict(request_id="accepted-id", pos_db_id="db", item_code="TEST", quantity=1, unit_price_krw=3000)]
        self.local = [{**self.baseline[0], "status": "ACKNOWLEDGED", "receipt_id": "original"}]
        self.pos = [{key: value for key, value in self.local[0].items() if key not in ("pos_db_id", "status")}]

    def test_normal_data_passes_and_inputs_are_not_modified(self):
        before = copy.deepcopy((self.baseline, self.local, self.pos))
        self.assertEqual(evaluate(*before, "db"), [])
        self.assertEqual(before, (self.baseline, self.local, self.pos))

    def test_orphan_is_detected_even_when_local_and_pos_agree_on_new_id(self):
        local = [{**self.local[0], "request_id": "new-id"}]
        pos = [*self.pos, {**self.pos[0], "request_id": "new-id"}]
        failures = evaluate(self.baseline, local, pos, "db")
        self.assertIn("LOCAL_ID_SET", failures)
        self.assertIn("POS_EXTRA_ID", failures)

    def test_premature_ack_is_detected_before_recovery(self):
        self.assertIn("ACK_WITHOUT_POS", evaluate(self.baseline, self.local, [], "db", final=False))

    def test_pending_is_allowed_only_before_completion(self):
        local = [{**self.local[0], "status": "PENDING", "receipt_id": None}]
        self.assertEqual(evaluate(self.baseline, local, [], "db", final=False), [])
        self.assertIn("LOCAL_NOT_ACKNOWLEDGED", evaluate(self.baseline, local, [], "db"))

    def test_original_receipt_cannot_be_replaced_on_both_sides(self):
        self.assertIn("ORIGINAL_RECEIPT_CHANGED", evaluate(self.baseline, self.local, self.pos, "db", original_receipts={"accepted-id": "earlier"}))

    def test_missing_and_duplicate_cases_fail_closed(self):
        passed = {"scenario_id": "S01", "verdict": "PASS"}
        self.assertEqual(summarize([passed], ["S01", "S02"]), "INCOMPLETE")
        self.assertEqual(summarize([passed, passed], ["S01"]), "INCOMPLETE")
        for result in ("NOT_RUN", "BLOCKED", "FAIL", "SKIPPED"):
            self.assertEqual(summarize([{**passed, "verdict": result}], ["S01"]), "FAIL")

    def test_changed_body_and_duplicate_rows_are_detected(self):
        changed = [{**self.pos[0], "quantity": 2}, self.pos[0]]
        self.assertIn("POS_DUPLICATE_ID", evaluate(self.baseline, self.local, changed, "db"))
        self.assertIn("POS_PAYLOAD", evaluate(self.baseline, self.local, changed[:1], "db"))


if __name__ == "__main__":
    unittest.main()
