#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from blockchain import LocalChain


def main() -> int:
    parser = argparse.ArgumentParser(description="Demonstrate blockchain verification failure after tampering")
    parser.add_argument("--result", type=Path, default=Path("artifacts/result.json"))
    parser.add_argument("--chain", type=Path, default=Path("artifacts/chain.json"))
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    chain = LocalChain.load(args.chain)
    item = args.chain and json.loads(args.chain.read_text())["chain"][-1]["records"][0]
    record_id = item["record_id"]
    original_ok = chain.verify_record(record_id, result)
    tampered = dict(result)
    tampered["text"] = tampered.get("text", "") + " [TAMPERED]"
    tampered_ok = chain.verify_record(record_id, tampered)
    print(f"Original record: {'✅ VERIFICATION PASSED' if original_ok else '❌ VERIFICATION FAILED'}")
    print(f"Changed one field: {'✅ UNEXPECTEDLY PASSED' if tampered_ok else '❌ VERIFICATION FAILED / TAMPERED'}")
    return 0 if original_ok and not tampered_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
