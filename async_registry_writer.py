from __future__ import annotations

import asyncio
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List


class AsyncRegistryWriter:
    """Drop-in async replacement for RegistryWriter.

    All write operations are non-blocking: they push a payload
    to an asyncio.Queue and a background task drains the queue,
    so the hot event-loop path is never blocked by disk I/O.

    Usage (in lifespan):
        writer = AsyncRegistryWriter(BASE / "runtime")
        writer_task = asyncio.create_task(writer.run())
        ...
        await writer.close()
    """

    def __init__(self, root: str | Path, maxsize: int = 2048):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._running = False
        self._task: asyncio.Task | None = None

        self.runs_file      = self.root / "registry_runs.jsonl"
        self.latest_file    = self.root / "latest_snapshot.json"
        self.specs_file     = self.root / "strategy_specs.jsonl"
        self.playbook_file  = self.root / "playbook_packets.jsonl"

    # ── Public async API ──────────────────────────────────────────
    async def write_snapshot(self, snapshot: Dict[str, Any]) -> None:
        payload = {"ts": datetime.now(UTC).isoformat(), "snapshot": snapshot}
        await self._enqueue("snapshot", payload)

    async def append_strategy_candidates(self, snapshot: Dict[str, Any]) -> None:
        ts = datetime.now(UTC).isoformat()
        rows = [
            {
                "ts": ts, "symbol": symbol,
                "strategy_name": name,
                "status": strategy.get("status"),
                "execution_ready": strategy.get("execution_ready"),
                "last_price": strategy.get("last_price"),
                "regime": state.get("regime_state", {}).get("regime"),
                "regime_confidence": state.get("regime_state", {}).get("confidence"),
            }
            for symbol, state in snapshot.items()
            for name, strategy in state.get("strategies", {}).items()
        ]
        if rows:
            await self._enqueue("candidates", rows)

    async def append_strategy_specs(self, specs: List[Dict[str, Any]]) -> None:
        if specs:
            await self._enqueue("specs", specs)

    async def append_playbook_packets(self, packets: List[Dict[str, Any]]) -> None:
        if packets:
            await self._enqueue("playbook", packets)

    # ── Background drain loop ─────────────────────────────────────
    async def run(self) -> None:
        self._running = True
        loop = asyncio.get_running_loop()
        while self._running or not self._q.empty():
            try:
                kind, payload = await asyncio.wait_for(self._q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await loop.run_in_executor(None, self._write_sync, kind, payload)
            self._q.task_done()

    async def close(self) -> None:
        self._running = False
        await self._q.join()

    # ── Synchronous file writes (offloaded to thread-pool) ────────
    def _write_sync(self, kind: str, payload: Any) -> None:
        if kind == "snapshot":
            self.latest_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif kind == "candidates":
            with self.runs_file.open("a", encoding="utf-8") as fh:
                for row in payload:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        elif kind == "specs":
            with self.specs_file.open("a", encoding="utf-8") as fh:
                for item in payload:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        elif kind == "playbook":
            with self.playbook_file.open("a", encoding="utf-8") as fh:
                for item in payload:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    async def _enqueue(self, kind: str, payload: Any) -> None:
        try:
            self._q.put_nowait((kind, payload))
        except asyncio.QueueFull:
            # Drop oldest, enqueue newest to avoid blocking
            try:
                self._q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await self._q.put((kind, payload))
