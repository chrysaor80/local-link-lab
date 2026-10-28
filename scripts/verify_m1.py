"""Compare immutable UI intent, committed Android result, and every POS row."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    root = Path("artifacts")
    baseline = json.loads((root / "m1-baseline.json").read_text(encoding="utf-8"))
    result = json.loads((root / "m1-result.json").read_text(encoding="utf-8"))
    with closing(sqlite3.connect((root / "m1-pos.db").resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM orders")]
        identity = conn.execute("SELECT db_id FROM metadata WHERE singleton = 1").fetchone()[0]
    require(len(rows) == 1, f"Expected exactly one POS row; got {len(rows)}")
    require(identity == baseline["pos_db_id"] == result["pos_db_id"], "POS DB identity differs")
    row = rows[0]
    for key in ("request_id", "item_code", "quantity", "unit_price_krw"):
        require(row[key] == baseline[key] == result[key], key)
    require(row["receipt_id"] == result["receipt_id"], "receipt_id differs")
    require(result["status"] == "ACKNOWLEDGED", "Android has not committed ACK")
    print("M1 PASS: UI intent, Room ACK, entire POS row set and receipt match (emulator NAT).")
    print(json.dumps({"baseline": baseline, "android_result": result, "pos_rows": rows}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, sqlite3.Error) as exc:
        print(f"M1 FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
