"""M2 red-team evidence script written by the reviewer against 127ea32 (not a product test).

python -m lab.m2_redteam_evidence

E1 models the S03_after_pos_commit hook in lab/android_run.py: after_commit holds the FIRST connection's
ACK. A retry of the same request takes the existing-row path (created=False), which skips the hook, so the
app can durably record the original receipt before force-stop if the harness is slower than one attempt
deadline. Nothing in android_run asserts that the order is still PENDING when the process is killed.

E2 shows that the observations used by S03 cannot tell a restored PENDING order from one that was
already delivered before the kill (e.g. by a build that ignores user_paused): evaluate(final=False)
returns no violation for both, and the only pause check is the persisted flag, not the behaviour.
"""
import asyncio
import json
from pathlib import Path
import tempfile
import uuid

from pos.server import PosServer
from pos.store import Store
from pos.wire import decode, encode
from .verdict import evaluate


async def held_ack_retry():
    with tempfile.TemporaryDirectory() as work:
        store = Store(Path(work) / "pos.db")
        release, committed = asyncio.Event(), asyncio.Event()

        async def after_commit(request, response):  # same shape as the S03_after_pos_commit branch
            committed.set()
            await release.wait()
            return True

        server = await PosServer(store, after_commit=after_commit).start()
        request = dict(version=1, type="submit_order", pos_db_id=store.db_id, request_id=str(uuid.uuid4()),
                       order=dict(item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000))
        try:
            _, first = await asyncio.open_connection("127.0.0.1", server.port)
            first.write(encode(request)); await first.drain()
            await asyncio.wait_for(committed.wait(), 5)
            first.close()  # the app's own attempt deadline closes the first socket
            reader, retry = await asyncio.open_connection("127.0.0.1", server.port)
            retry.write(encode(request)); await retry.drain()
            try:
                reply = decode(await asyncio.wait_for(reader.readuntil(b"\n"), 1.0))
            except asyncio.TimeoutError:
                reply = None
            retry.close()
            return {"ack_still_held": not release.is_set(), "retry_reply_type": reply and reply["type"],
                    "retry_got_receipt": bool(reply and reply.get("receipt_id"))}
        finally:
            release.set()
            await server.close()


def restore_phase_blind_spot():
    rid, db, receipt = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    baseline = [dict(request_id=rid, pos_db_id=db, item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000)]
    pending_local = [{**baseline[0], "status": "PENDING", "receipt_id": None}]
    delivered_local = [{**baseline[0], "status": "ACKNOWLEDGED", "receipt_id": receipt}]
    delivered_pos = [dict(request_id=rid, receipt_id=receipt, item_code="DEMO_COFFEE", quantity=1, unit_price_krw=3000)]
    return {
        "restored_pending_when_really_pending": evaluate(baseline, pending_local, [], db, final=False),
        "restored_pending_when_already_delivered": evaluate(baseline, delivered_local, delivered_pos, db, final=False),
        "final_when_already_delivered": evaluate(baseline, delivered_local, delivered_pos, db, final=True,
                                                 original_receipts={rid: receipt}),
    }


if __name__ == "__main__":
    print(json.dumps({"E1_held_ack_retry": asyncio.run(held_ack_retry()),
                      "E2_restore_phase": restore_phase_blind_spot()}, indent=2))
