# FaceChain — HH Goa 2026 Task 3

FaceChain is a simple CLI demonstration of the required pipeline:

> **Face scan → genuine live web/social search → matching real post → blockchain anchoring → independent blockchain re-verification**

It is designed for a **consented subject**. The reference photo must be supplied by the subject or used with explicit permission. This project must not be used to identify strangers, deanonymize people, monitor people, or infer identity without consent.

## What the final pipeline does

| Stage | What happens | Visible evidence |
|---|---|---|
| Face scan | OpenCV detects exactly one face and creates a normalized face descriptor. | `Face detected and encoded` |
| Genuine search | The program uses Bluesky’s live public `searchPosts` API for normal queries, or performs a live X profile-page search plus public post retrieval when the query begins with `x:`. It does not contain a pre-selected post. | Source, query, post count, and image count |
| Candidate comparison | Every image in the retrieved posts is downloaded, faces are detected, and all face-bearing candidates are scored. | Number checked, best URL, distance, similarity |
| Fingerprint | The selected post metadata is canonicalized and hashed with SHA-256. The image is also hashed. | Fingerprint values in `result.json` |
| Blockchain | The fingerprint is recorded in a deterministic local hash chain. | Block hash and transaction hash |
| Re-verification | The fingerprint is retrieved from the chain and compared with an independently recomputed fingerprint. | `✅ BLOCKCHAIN VERIFICATION PASSED` |

## Blockchain choice

The project uses a **local simulated blockchain**. This is explicitly allowed by the challenge and makes the demo deterministic, free, and runnable without a wallet, RPC key, gas, or network dependency. Each record has a transaction hash, block hash, previous-block hash, and stored fingerprint. The implementation validates every block link before comparing hashes.

A real Polygon Amoy deployment could strengthen the presentation, but it would require a funded testnet wallet, RPC endpoint, contract deployment, secret management, and additional operational failure modes. The current local chain is therefore the more reliable submission path; the README states the limitation transparently.

## Setup

```bash
sudo apt-get update
sudo apt-get install -y libglib2.0-0 libgl1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Successful demo command

Put a consented, single-face image at `examples/reference.png`. Use an authorized public search query. For a reliable demonstration, the query should be a distinctive phrase or public handle that returns posts containing the subject’s image.

```bash
python facechain.py \
  --reference examples/reference.png \
  --query "authorized-public-query" \
  --limit 50 \
  --threshold 1.20
```

The program writes `artifacts/result.json` and `artifacts/chain.json` and visibly prints:

```text
Face detected and encoded
Live search performed
Candidates retrieved
Best matching post found
Post fingerprint generated
Blockchain transaction submitted
On-chain fingerprint retrieved
Hashes compared
✅ BLOCKCHAIN VERIFICATION PASSED
```

For this reference image, the reproducible live-search command is `--query 'x:Aryannn_6476476'`. The program discovers post IDs from the public X profile page, retrieves those posts through a public endpoint, and compares their media; the matching post URL is not hardcoded. A normal query without the `x:` prefix uses Bluesky’s live search API.

## Tamper demonstration

After one successful run, execute:

```bash
python tamper_demo.py
```

Expected output:

```text
Original record: ✅ VERIFICATION PASSED
Changed one field: ❌ VERIFICATION FAILED / TAMPERED
```

This changes only an in-memory copy of one saved field; the original `artifacts/result.json` remains unchanged. You can also independently verify the original record with:

```bash
python blockchain.py --result artifacts/result.json --chain artifacts/chain.json
```

## Screen-recording sequence

Show the reference image, run the successful command, pause on the live query and candidate counts, show the selected real post URL, open `artifacts/result.json`, open `artifacts/chain.json`, run `python blockchain.py ...`, and finish with `python tamper_demo.py` showing the failed tampered verification.

## Known limitations

Bluesky and X public endpoints, profile/post availability, search ranking, rate limits, and image URLs can change. The lightweight OpenCV descriptor is a demonstration signal, not an identity proof, and the threshold should be validated on the consented demo data. A local simulated chain is not equivalent to a public blockchain explorer record. The program stores post metadata and hashes rather than the downloaded social-media image.

## References

[1]: https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html "OpenCV cascade classifier documentation"
[2]: https://docs.bsky.app/docs/api/app-bsky-feed-search-posts "Bluesky searchPosts API"
[3]: https://docs.python.org/3/library/hashlib.html "Python hashlib documentation"
