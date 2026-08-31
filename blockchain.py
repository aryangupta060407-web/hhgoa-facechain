from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class LocalChain:
    """Small deterministic simulated blockchain for a reproducible offline demo."""

    def __init__(self, blocks: list[dict[str, Any]] | None = None):
        self.blocks = blocks or [self._genesis()]

    @staticmethod
    def _genesis() -> dict[str, Any]:
        block = {"index": 0, "timestamp": 0, "previous_hash": "0" * 64, "records": []}
        block["hash"] = hashlib.sha256(canonical(block)).hexdigest()
        return block

    @staticmethod
    def _block_hash(block: dict[str, Any]) -> str:
        body = {k: v for k, v in block.items() if k != "hash"}
        return hashlib.sha256(canonical(body)).hexdigest()

    def add_record(self, record: dict[str, Any]) -> dict[str, Any]:
        record_id = str(uuid.uuid4())
        fingerprint = hashlib.sha256(canonical(record)).hexdigest()
        previous = self.blocks[-1]
        block = {
            "index": len(self.blocks),
            "timestamp": int(time.time()),
            "previous_hash": previous["hash"],
            "records": [{"record_id": record_id, "fingerprint": fingerprint}],
        }
        block["hash"] = self._block_hash(block)
        self.blocks.append(block)
        return {"record_id": record_id, "fingerprint": fingerprint, "block_index": block["index"], "block_hash": block["hash"]}

    def verify_record(self, record_id: str, record: dict[str, Any]) -> bool:
        expected = hashlib.sha256(canonical(record)).hexdigest()
        for block in self.blocks:
            if not self._block_hash(block) == block.get("hash"):
                return False
            for item in block.get("records", []):
                if item.get("record_id") == record_id:
                    return item.get("fingerprint") == expected
        return False

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"chain": self.blocks}, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> "LocalChain":
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text()).get("chain", []))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Re-verify a saved result against the simulated chain")
    parser.add_argument("--result", type=Path, default=Path("artifacts/result.json"))
    parser.add_argument("--chain", type=Path, default=Path("artifacts/chain.json"))
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    tx = json.loads(args.chain.read_text())["chain"][-1]["records"][0]
    print({"record_id": tx["record_id"], "verified": LocalChain.load(args.chain).verify_record(tx["record_id"], result)})
