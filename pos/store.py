"""One durable database identity and one durable row per request."""
from contextlib import closing
from pathlib import Path
import sqlite3
import uuid

from .wire import error


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        # Only explicit initialization may create a database file.
        with closing(self.connect(create=True)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), db_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orders (
                    request_id TEXT PRIMARY KEY, receipt_id TEXT UNIQUE NOT NULL,
                    item_code TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_krw INTEGER NOT NULL
                );
            """)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO metadata VALUES(1,?)", (str(uuid.uuid4()),))
            conn.commit()

    def connect(self, *, create=False):
        uri = Path(self.path).as_uri() + ("?mode=rwc" if create else "?mode=rw")
        conn = sqlite3.connect(uri, uri=True, timeout=1.0, isolation_level=None)
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=1000")
        return conn

    @property
    def db_id(self):
        with closing(self.connect()) as conn:
            row = conn.execute("SELECT db_id FROM metadata WHERE singleton=1").fetchone()
            if row is None:
                raise sqlite3.DatabaseError("POS identity is missing")
            return row[0]

    def submit(self, message):
        rid, body = message["request_id"], message["order"]
        values = (body["item_code"], body["quantity"], body["unit_price_krw"])
        with closing(self.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            actual_db = conn.execute("SELECT db_id FROM metadata WHERE singleton=1").fetchone()[0]
            if actual_db != message["pos_db_id"]:
                conn.rollback()
                return error(actual_db, rid, "POS_MISMATCH"), False
            old = conn.execute("SELECT receipt_id,item_code,quantity,unit_price_krw FROM orders WHERE request_id=?", (rid,)).fetchone()
            if old:
                conn.commit()
                if tuple(old[1:]) != values:
                    return error(actual_db, rid, "ID_CONFLICT"), False
                receipt, created = old[0], False
            else:
                receipt, created = str(uuid.uuid4()), True
                conn.execute("INSERT INTO orders VALUES(?,?,?,?,?)", (rid, receipt, *values))
                conn.commit()
            return dict(version=1, type="ack", pos_db_id=actual_db, request_id=rid, receipt_id=receipt), created
