"""Scenario preconditions are stricter than generic eventual-delivery invariants."""


def pending(rows):
    return bool(rows) and all(row.get("status") == "PENDING" and row.get("receipt_id") is None for row in rows)


def paused_violations(snapshot, pos_rows, submit_count):
    violations = []
    if not snapshot.get("user_paused"):
        violations.append("USER_PAUSE_LOST")
    if not pending(snapshot["rows"]) or pos_rows or submit_count:
        violations.append("SENT_WHILE_PAUSED")
    return violations


def commit_window(snapshot, pos_rows, receipts, released_acks):
    """False means this run cannot claim process death before ACK delivery."""
    return (pending(snapshot["rows"]) and len(pos_rows) == 1 and len(receipts) == 1
            and pos_rows[0]["receipt_id"] == receipts.get(pos_rows[0]["request_id"])
            and released_acks == 0)
