"""Run: python -m pos.server --db artifacts/pos.db --host 127.0.0.1."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
import json
from pathlib import Path
import sqlite3

from .store import Store
from .wire import MAX_FRAME, InvalidFrame, decode, encode, error


class PosServer:
    def __init__(self, store, *, read_timeout=5.0, write_timeout=1.0, max_connections=32, after_commit=None):
        self.store = store
        self.read_timeout, self.write_timeout = read_timeout, write_timeout
        self.max_connections, self.after_commit = max_connections, after_commit
        self.tasks = set()
        self.db_tasks = set()
        self.server = None

    async def start(self, host="127.0.0.1", port=0):
        self.server = await asyncio.start_server(self._handle, host, port, limit=MAX_FRAME)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def close(self):
        self.server.close()
        await self.server.wait_closed()
        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        # Cancelling a socket handler cannot cancel a SQLite worker thread.
        # Drain it before callers can remove/replace the database.
        if self.db_tasks:
            await asyncio.gather(*list(self.db_tasks), return_exceptions=True)

    async def identity(self):
        # Read the same file used by submit; a deleted/unreadable DB cannot certify an old ID.
        task = asyncio.create_task(asyncio.to_thread(lambda: self.store.db_id))
        self.db_tasks.add(task)
        task.add_done_callback(self.db_tasks.discard)
        return await asyncio.shield(task)

    async def _handle(self, reader, writer):
        task = asyncio.current_task()
        if len(self.tasks) >= self.max_connections:
            writer.close()
            with suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), self.write_timeout)
            return
        self.tasks.add(task)
        rid = None
        try:
            frame = await asyncio.wait_for(reader.readuntil(b"\n"), self.read_timeout)
            try:
                request = decode(frame)
                rid = request.get("request_id")
            except InvalidFrame as exc:
                response = error(await self.identity(), exc.request_id, exc.code)
            else:
                if request["type"] == "hello":
                    response = dict(version=1, type="hello_ack", pos_db_id=await self.identity())
                elif request["type"] == "submit_order":
                    # Separate connection in a worker thread; lock waits do not block other sockets.
                    db_task = asyncio.create_task(asyncio.to_thread(self.store.submit, request))
                    self.db_tasks.add(db_task)
                    db_task.add_done_callback(self.db_tasks.discard)
                    response, created = await asyncio.shield(db_task)
                    if created:
                        print(json.dumps({"event": "POS_COMMITTED", "request_id": rid, "receipt_id": response["receipt_id"]}), flush=True)
                        if self.after_commit is not None and not await self.after_commit(request, response):
                            return
                else:
                    response = error(await self.identity(), rid, "INVALID_REQUEST")
            writer.write(encode(response))
            await asyncio.wait_for(writer.drain(), self.write_timeout)
        except sqlite3.Error:
            # A commit may already have happened: never claim definitive rejection here.
            with suppress(Exception):
                writer.write(encode(error(await self.identity(), rid, "TEMPORARY_UNAVAILABLE")))
                await asyncio.wait_for(writer.drain(), self.write_timeout)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            pass
        finally:
            writer.close()
            with suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), self.write_timeout)
            self.tasks.discard(task)


async def main(args):
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db)
    server = await PosServer(store).start(args.host, args.port)
    print(json.dumps({"event": "LISTENING", "host": args.host, "port": server.port, "pos_db_id": store.db_id}), flush=True)
    try:
        async with server.server:
            await server.server.serve_forever()
    finally:
        await server.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="artifacts/pos.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
