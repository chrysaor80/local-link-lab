"""M1 red-team reproductions written by the reviewer against ee67e2c.

Adopted by Codex; see docs/reviews/M1_RESPONSE.md for changes to the original patch.
Each test states its expected outcome at that snapshot. "Regression" tests are expected to
PASS and only lock in current behaviour; they are not failure reproductions.
"""
import asyncio
from contextlib import closing, suppress
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from .server import PosServer
from .store import Store
from .wire import decode, encode

ROOT = Path(__file__).resolve().parents[1]


class RedTeamPosTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "pos.db")
        self.server = await PosServer(self.store, read_timeout=0.5).start()

    async def asyncTearDown(self):
        await self.server.close()
        self.directory.cleanup()

    def submit(self, db_id=None):
        return dict(version=1, type="submit_order", pos_db_id=db_id or self.store.db_id,
                    request_id=str(uuid.uuid4()), order=dict(item_code="COFFEE", quantity=1, unit_price_krw=4500))

    async def send(self, request, timeout=6.0):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        try:
            writer.write(encode(request)); await writer.drain()
            return decode(await asyncio.wait_for(reader.readuntil(b"\n"), timeout))
        finally:
            writer.close(); await writer.wait_closed()

    def rows(self):
        with closing(self.store.connect()) as conn:
            return conn.execute("SELECT request_id FROM orders").fetchall()

    async def test_writer_lock_is_temporary_unavailable_within_client_budget(self):
        """Regression, expected PASS: busy/locked answers before the 5 s client attempt budget."""
        blocker = sqlite3.connect(self.store.path, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        try:
            started = time.monotonic()
            reply = await self.send(self.submit())
            elapsed = time.monotonic() - started
        finally:
            blocker.rollback(); blocker.close()
        self.assertEqual(reply["code"], "TEMPORARY_UNAVAILABLE")
        self.assertLess(elapsed, 2.5)
        self.assertEqual(self.rows(), [])

    async def test_trickled_whitespace_does_not_extend_read_deadline(self):
        """Regression, expected PASS: bytes without LF do not restart the 0.5 s server deadline."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        started, closed_after = time.monotonic(), None
        try:
            for _ in range(60):
                try:
                    writer.write(b" "); await writer.drain()
                    if await asyncio.wait_for(reader.read(1), 0.05) == b"":
                        closed_after = time.monotonic() - started; break
                except asyncio.TimeoutError:
                    pass
                except ConnectionError:
                    closed_after = time.monotonic() - started; break
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
        self.assertIsNotNone(closed_after, "server kept a trickling connection open for 3 s")
        self.assertLess(closed_after, 1.2)

    async def test_hello_reports_the_database_that_handles_orders(self):
        """Expected FAIL at ee67e2c: hello_ack uses Store.db_id cached at start-up,
        while submit reads metadata inside its transaction. Safety still holds (POS_MISMATCH, no write)."""
        old_id = self.store.db_id
        other_dir = tempfile.TemporaryDirectory()
        self.addCleanup(other_dir.cleanup)
        other = Store(Path(other_dir.name) / "other.db")
        for suffix in ("-wal", "-shm"):
            with suppress(FileNotFoundError):
                os.remove(self.store.path + suffix)
        shutil.copyfile(other.path, self.store.path)  # the served file changes under a running POS
        hello = await self.send(dict(version=1, type="hello"))
        mismatch = await self.send(self.submit(db_id=old_id))
        self.assertEqual(mismatch["code"], "POS_MISMATCH")
        self.assertEqual(hello["pos_db_id"], mismatch["pos_db_id"],
                         "hello certified a database that no longer serves orders")
        self.assertEqual(hello["pos_db_id"], other.db_id)
        self.assertEqual(self.rows(), [])
        accepted = await self.send(self.submit(db_id=hello["pos_db_id"]))
        self.assertEqual(accepted["type"], "ack")
        self.assertEqual(len(self.rows()), 1)

    async def test_deleted_database_is_not_recreated_by_hello(self):
        Path(self.store.path).unlink()
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.send(dict(version=1, type="hello"))
        self.assertFalse(Path(self.store.path).exists())


class VerifierFailClosedTest(unittest.TestCase):
    def test_verify_m1_rejects_orphan_row_even_with_python_optimize(self):
        """Expected FAIL at ee67e2c for flags=['-O']: verify_m1.py relies on assert,
        which -O or PYTHONOPTIMIZE removes, so it prints 'M1 PASS' for an orphan POS row."""
        with tempfile.TemporaryDirectory() as work:
            artifacts = Path(work) / "artifacts"
            artifacts.mkdir()
            store = Store(artifacts / "m1-pos.db")
            rid, receipt = str(uuid.uuid4()), str(uuid.uuid4())
            baseline = dict(request_id=rid, pos_db_id=store.db_id, item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000)
            (artifacts / "m1-baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            (artifacts / "m1-result.json").write_text(
                json.dumps({**baseline, "receipt_id": receipt, "status": "ACKNOWLEDGED"}), encoding="utf-8")
            with closing(store.connect()) as conn:
                conn.execute("INSERT INTO orders VALUES(?,?,?,?,?)", (rid, receipt, "DEMO_COFFEE", 1, 3000))
            for flags in ([], ["-O"]):
                proc = subprocess.run([sys.executable, *flags, str(ROOT / "scripts" / "verify_m1.py")],
                                      cwd=work, capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)  # the verifier can also accept valid evidence
            with closing(store.connect()) as conn:
                conn.execute("INSERT INTO orders VALUES(?,?,?,?,?)",
                             (str(uuid.uuid4()), str(uuid.uuid4()), "DEMO_COFFEE", 1, 3000))  # orphan order
            for flags in ([], ["-O"]):
                with self.subTest(flags=flags):
                    proc = subprocess.run([sys.executable, *flags, str(ROOT / "scripts" / "verify_m1.py")],
                                          cwd=work, capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
