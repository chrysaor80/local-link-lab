"""Regressions for M2 review findings; real TCP for the replay barrier, pure phase/identity checks."""
import asyncio
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

from pos.server import PosServer
from pos.store import Store
from pos.wire import encode, decode
from .identity import clean_source, installed_apk
from .phases import paused_violations, commit_window


class PhaseTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"user_paused": True, "rows": [{"status": "PENDING", "receipt_id": None}]}

    def test_pause_requires_pending_no_pos_effect_and_no_attempt(self):
        self.assertEqual(paused_violations(self.snapshot, [], 0), [])
        self.assertIn("SENT_WHILE_PAUSED", paused_violations(self.snapshot, [], 1))
        self.assertIn("SENT_WHILE_PAUSED", paused_violations(self.snapshot, [{"request_id": "x"}], 0))
        self.snapshot["rows"][0].update(status="ACKNOWLEDGED", receipt_id="receipt")
        self.assertIn("SENT_WHILE_PAUSED", paused_violations(self.snapshot, [], 0))

    def test_commit_window_rejects_missing_commit_or_ack_delivered_before_death(self):
        rows, receipts = [{"request_id": "x", "receipt_id": "r"}], {"x": "r"}
        self.assertTrue(commit_window(self.snapshot, rows, receipts, 0))
        self.assertFalse(commit_window(self.snapshot, [], receipts, 0))
        self.assertFalse(commit_window(self.snapshot, rows, receipts, 1))
        self.snapshot["rows"][0].update(status="ACKNOWLEDGED", receipt_id="r")
        self.assertFalse(commit_window(self.snapshot, rows, receipts, 0))


class AckBarrierTest(unittest.IsolatedAsyncioTestCase):
    async def test_retry_cannot_bypass_held_ack_and_reuses_original_receipt(self):
        with tempfile.TemporaryDirectory() as work:
            store = Store(Path(work) / "pos.db")
            arrivals, release = asyncio.Queue(), asyncio.Event()

            async def hold(request, response):
                await arrivals.put(response["receipt_id"])
                await release.wait()
                return True

            server = await PosServer(store, before_ack=hold).start()
            writers = []
            request = dict(version=1, type="submit_order", pos_db_id=store.db_id, request_id=str(uuid.uuid4()),
                           order=dict(item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000))
            try:
                _, first = await asyncio.open_connection("127.0.0.1", server.port)
                writers.append(first)
                first.write(encode(request)); await first.drain()
                original = await asyncio.wait_for(arrivals.get(), 2)
                first.close(); await first.wait_closed()  # model the expired first attempt
                reader, retry = await asyncio.open_connection("127.0.0.1", server.port)
                writers.append(retry)
                retry.write(encode(request)); await retry.drain()
                self.assertEqual(await asyncio.wait_for(arrivals.get(), 2), original)
                with self.assertRaises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readuntil(b"\n"), 0.1)
                release.set()
                reply = decode(await asyncio.wait_for(reader.readuntil(b"\n"), 2))
                self.assertEqual(reply["receipt_id"], original)
                conn = store.connect()
                try:
                    self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], 1)
                finally:
                    conn.close()
            finally:
                release.set()
                for writer in writers:
                    writer.close()
                    await writer.wait_closed()
                await server.close()


class IdentityTest(unittest.IsolatedAsyncioTestCase):
    async def test_hash_is_computed_from_installed_bytes_not_pm_path(self):
        class Adb:
            content = b"apk"
            async def run(self, *args, **kwargs):
                return self.content if kwargs.get("binary") else "package:/data/app/example/base.apk"
        with tempfile.TemporaryDirectory() as work:
            apk = Path(work) / "app.apk"
            apk.write_bytes(b"apk")
            adb = Adb()
            self.assertEqual((await installed_apk(adb, apk))["installed_sha256"], hashlib.sha256(b"apk").hexdigest())
            adb.content = b"stale-apk"
            with self.assertRaisesRegex(ValueError, "differs"):
                await installed_apk(adb, apk)

    async def test_uncommitted_inputs_cannot_be_labelled_with_head(self):
        with tempfile.TemporaryDirectory() as work:
            def git(*args):
                return subprocess.run(["git", *args], cwd=work, check=True, capture_output=True)
            git("init")
            source = Path(work) / "source.txt"
            source.write_text("baseline")
            git("add", "source.txt")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
            self.assertEqual(len(clean_source(work)), 40)
            source.write_text("uncommitted")
            with self.assertRaisesRegex(ValueError, "dirty"):
                clean_source(work)
            git("checkout", "--", "source.txt")
            (Path(work) / "new-source.txt").write_text("untracked")
            with self.assertRaisesRegex(ValueError, "dirty"):
                clean_source(work)


if __name__ == "__main__":
    unittest.main()
