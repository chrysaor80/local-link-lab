import asyncio
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from .server import PosServer
from .store import Store
from .wire import InvalidFrame, decode, encode


class RawContractTest(unittest.TestCase):
    def test_shared_raw_corpus(self):
        expected = json.loads((Path(__file__).parents[1] / "spec/wire.error-expectations.json").read_text())
        for example in json.loads((Path(__file__).parents[1] / "spec/wire.raw-examples.json").read_text()):
            with self.subTest(name=example["name"]):
                frame = bytes.fromhex(example["frame_hex"])
                if example["expected_valid"]:
                    decode(frame)
                else:
                    with self.assertRaises(InvalidFrame) as caught:
                        decode(frame)
                    self.assertEqual(caught.exception.code, expected[example["name"]]["code"])
                    self.assertEqual(caught.exception.request_id, expected[example["name"]]["request_id"])


class RealTcpTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "pos.db")
        self.server = await PosServer(self.store, read_timeout=0.3).start()
        self.request = dict(version=1, type="submit_order", pos_db_id=self.store.db_id,
                            request_id=str(uuid.uuid4()), order=dict(item_code="COFFEE", quantity=1, unit_price_krw=4500))

    async def asyncTearDown(self):
        await self.server.close()
        self.directory.cleanup()

    async def send(self, request):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        try:
            writer.write(encode(request)); await writer.drain()
            return decode(await asyncio.wait_for(reader.readuntil(b"\n"), 2))
        finally:
            writer.close(); await writer.wait_closed()

    def rows(self):
        with closing(self.store.connect()) as conn:
            return conn.execute("SELECT request_id,item_code,quantity,unit_price_krw,receipt_id FROM orders").fetchall()

    async def test_roundtrip_and_db_identity_survive_restart(self):
        hello = await self.send(dict(version=1, type="hello"))
        ack = await self.send(self.request)
        self.assertEqual(hello["pos_db_id"], self.store.db_id)
        self.assertEqual(self.rows(), [(self.request["request_id"], "COFFEE", 1, 4500, ack["receipt_id"])])
        restarted = Store(self.store.path)
        self.assertEqual(restarted.db_id, self.store.db_id)
        response, created = restarted.submit(self.request)
        self.assertFalse(created); self.assertEqual(response, ack)

    async def test_concurrent_duplicates_and_conflict(self):
        replies = await asyncio.gather(*(self.send(self.request) for _ in range(8)))
        self.assertTrue(all(reply == replies[0] for reply in replies))
        self.assertEqual(len(self.rows()), 1)
        changed = {**self.request, "order": {**self.request["order"], "quantity": 2}}
        self.assertEqual((await self.send(changed))["code"], "ID_CONFLICT")
        self.assertEqual(self.rows()[0][2], 1)

    async def test_commit_then_lost_ack_retries_to_original_receipt(self):
        committed = []
        async def drop(request, response):
            committed.append(response); return False
        self.server.after_commit = drop
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.send(self.request)
        ack = await self.send(self.request)
        self.assertEqual(ack, committed[0])
        # Whole database, compared with a baseline captured before any application mutation.
        self.assertEqual(self.rows(), [(self.request["request_id"], "COFFEE", 1, 4500, ack["receipt_id"])])

    async def test_idle_client_does_not_block_and_is_closed(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        try:
            ack = await self.send(self.request)
            self.assertEqual(ack["type"], "ack")
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        finally:
            writer.close(); await writer.wait_closed()

    async def test_changed_database_is_rejected_before_write(self):
        changed = {**self.request, "pos_db_id": str(uuid.uuid4())}
        self.assertEqual((await self.send(changed))["code"], "POS_MISMATCH")
        self.assertEqual(self.rows(), [])

    async def test_error_code_and_correlation_over_tcp_without_writes(self):
        root = Path(__file__).parents[1] / "spec"
        expected = json.loads((root / "wire.error-expectations.json").read_text())
        for example in json.loads((root / "wire.raw-examples.json").read_text()):
            frame = bytes.fromhex(example["frame_hex"])
            # Framing EOF/overflow and two concatenated frames have distinct connection semantics.
            if example["expected_valid"] or example["name"] in {"missing_lf", "oversized", "two_frames"}:
                continue
            with self.subTest(name=example["name"]):
                reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
                try:
                    writer.write(frame)
                    await writer.drain()
                    reply = decode(await asyncio.wait_for(reader.readuntil(b"\n"), 2))
                    self.assertEqual(reply["type"], "error")
                    self.assertEqual(reply["pos_db_id"], self.store.db_id)
                    self.assertEqual(reply["code"], expected[example["name"]]["code"])
                    self.assertEqual(reply["request_id"], expected[example["name"]]["request_id"])
                finally:
                    writer.close()
                    await writer.wait_closed()
        self.assertEqual(self.rows(), [])

    async def test_binary_lf_response_and_split_request(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        try:
            frame = encode(self.request)
            for byte in frame:
                writer.write(bytes([byte])); await writer.drain()
            response = await asyncio.wait_for(reader.readuntil(b"\n"), 1)
            self.assertNotIn(b"\r", response)
            self.assertEqual(decode(response)["type"], "ack")
        finally:
            writer.close(); await writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
