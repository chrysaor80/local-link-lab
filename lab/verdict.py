"""Data invariants independent of the client implementation and mutation mechanism."""
from collections import Counter

BODY = ("item_code", "quantity", "unit_price_krw")


def evaluate(baseline, local_rows, pos_rows, pos_db_id, *, final=True, original_receipts=None):
    """Return stable violation codes. An interim PENDING row is allowed; false ACK is never allowed."""
    failures = []
    if not baseline or len({row["request_id"] for row in baseline}) != len(baseline):
        return ["INVALID_BASELINE"]
    expected = {row["request_id"]: row for row in baseline}
    local = {row["request_id"]: row for row in local_rows}
    pos = {row["request_id"]: row for row in pos_rows}
    if Counter(row["request_id"] for row in local_rows) != Counter(expected.keys()):
        failures.append("LOCAL_ID_SET")
    if len(pos) != len(pos_rows):
        failures.append("POS_DUPLICATE_ID")
    if set(pos) - set(expected):
        failures.append("POS_EXTRA_ID")
    if final and Counter(row["request_id"] for row in pos_rows) != Counter(expected.keys()):
        failures.append("POS_ID_SET")
    for rid, row in expected.items():
        if row["pos_db_id"] != pos_db_id:
            failures.append("POS_IDENTITY")
        if rid in local:
            actual = local[rid]
            if any(actual.get(key) != row[key] for key in (*BODY, "pos_db_id")):
                failures.append("LOCAL_PAYLOAD")
            if actual.get("status") == "ACKNOWLEDGED":
                if rid not in pos:
                    failures.append("ACK_WITHOUT_POS")
                elif not actual.get("receipt_id") or actual["receipt_id"] != pos[rid]["receipt_id"]:
                    failures.append("RECEIPT_MISMATCH")
            elif final:
                failures.append("LOCAL_NOT_ACKNOWLEDGED")
        if rid in pos:
            if any(pos[rid].get(key) != row[key] for key in BODY):
                failures.append("POS_PAYLOAD")
            if original_receipts and rid in original_receipts and pos[rid]["receipt_id"] != original_receipts[rid]:
                failures.append("ORIGINAL_RECEIPT_CHANGED")
    return sorted(set(failures))


def summarize(results, required):
    """Missing, duplicate, skipped or blocked executions cannot produce an all-pass gate."""
    counts = Counter(result["scenario_id"] for result in results)
    if not required or set(counts) != set(required) or any(count != 1 for count in counts.values()):
        return "INCOMPLETE"
    return "PASS" if all(result["verdict"] == "PASS" for result in results) else "FAIL"
