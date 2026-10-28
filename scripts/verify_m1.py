"""Compare immutable UI intent, committed Android result, and every POS row."""
import json
from pathlib import Path
import sqlite3

root = Path("artifacts")
baseline = json.loads((root / "m1-baseline.json").read_text(encoding="utf-8"))
result = json.loads((root / "m1-result.json").read_text(encoding="utf-8"))
with sqlite3.connect(root / "m1-pos.db") as conn:
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute("SELECT * FROM orders")]
    identity = conn.execute("SELECT db_id FROM metadata WHERE singleton = 1").fetchone()[0]
assert len(rows) == 1, f"Expected exactly one POS row; got {len(rows)}"
assert identity == baseline["pos_db_id"] == result["pos_db_id"]
row = rows[0]
for key in ("request_id", "item_code", "quantity", "unit_price_krw"):
    assert row[key] == baseline[key] == result[key], key
assert row["receipt_id"] == result["receipt_id"]
assert result["status"] == "ACKNOWLEDGED"
print("M1 PASS: UI intent, Room ACK, entire POS row set and receipt match (emulator NAT).")
print(json.dumps({"baseline": baseline, "android_result": result, "pos_rows": rows}, ensure_ascii=True))
