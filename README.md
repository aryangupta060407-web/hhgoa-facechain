# FaceChain: Consent-Based Face Match → Web Evidence → Blockchain Verification

FaceChain is a command-line proof of concept for a **consented subject**. It detects and encodes exactly one face from a supplied reference image using an OpenCV Haar detector and normalized 64×64 face descriptor, performs a genuine live search against Bluesky's public search API, downloads candidate post images, compares their detected face descriptors, and anchors the discovered post's canonical metadata fingerprint on a small local simulated blockchain. It then re-verifies the same record against the on-chain fingerprint.

> **Responsible-use boundary:** This demo is intended only for a person who has explicitly provided the reference image and authorized the search. It must not be used to identify strangers, deanonymize people, monitor people, or infer identity without consent. The local chain is a transparent testnet-style simulation, not a production public chain.

## Pipeline

| Stage | Implementation | Evidence shown in the demo |
|---|---|---|
| Face scan | OpenCV Haar detector and normalized 4,096-value face descriptor | Detected one face and generated a descriptor |
| Genuine web search | Bluesky public `app.bsky.feed.searchPosts` API | Live query, post URL, retrieved image URL, and post text |
| Candidate matching | Face distance against faces found in returned public post images | Numeric face distance and threshold |
| Blockchain anchoring | Deterministic local hash chain in `artifacts/chain.json` | Record fingerprint, block hash, and previous hash |
| Re-verification | Recompute canonical JSON SHA-256 and validate chain linkage | `blockchain verification = True` |

## Setup

Python 3.10+ is recommended. On Ubuntu, install the native build prerequisites and Python packages:

```bash
sudo apt-get update
sudo apt-get install -y libglib2.0-0 libgl1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

Place a **single-face, consented reference image** at `examples/reference.png`. For the strongest demo, use the authorized public X post supplied by the subject:

```bash
python facechain.py \
  --reference examples/reference.png \
  --x-url "https://x.com/Aryannn_6476476/status/2086348435729575971?s=20" \
  --threshold 1.20
```

The same program also supports a genuine Bluesky search when an authorized public query is available:

```bash
python facechain.py --reference examples/reference.png --query "authorized-public-handle.bsky.social" --limit 50
```

The command writes `artifacts/result.json` and `artifacts/chain.json`. A successful run prints the real public-post URL, the face distance, the block fingerprint, and:

```text
SUCCESS: blockchain verification = True
```

Re-run verification independently:

```bash
python blockchain.py --result artifacts/result.json --chain artifacts/chain.json
```

To demonstrate tamper evidence for the recording, make a copy of `artifacts/result.json`, change one character in its text field, and run the verifier against the modified copy. Verification must become `False`; restore the original afterward.

## Screen recording script

1. Show the repository and the consented reference image without exposing unnecessary personal information.
2. Run the main command. Pause on the face-detection message, the live Bluesky query, and the discovered public post URL.
3. Scroll through `artifacts/result.json` to show the source, query, post URL, timestamp, image SHA-256, and face distance.
4. Open `artifacts/chain.json` and show the record fingerprint, block hash, and previous hash.
5. Run `python blockchain.py ...` and show `verified: True`.
6. Optionally edit only a copy of the result JSON and show that verification fails, then restore the original and show that it passes again.

## Known limitations

The Bluesky endpoint returns public search results and availability can change. Search ranking, rate limits, deleted posts, private accounts, inaccessible images, and image quality can prevent a match. The descriptor distance is not an identity proof and the threshold requires validation for the chosen data. The local blockchain is a deterministic simulated chain for judging and reproducibility; a production deployment should replace it with a public testnet smart contract or a managed timestamping service. The system stores hashes and metadata, not the downloaded post image itself.

## References

[1]: https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html "OpenCV cascade classifier documentation"
[2]: https://docs.bsky.app/docs/api/app-bsky-feed-search-posts "Bluesky searchPosts API"
[3]: https://docs.python.org/3/library/hashlib.html "Python hashlib documentation"
