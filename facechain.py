#!/usr/bin/env python3
"""Consent-based face scan -> live social search -> matching post -> chain verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from blockchain import LocalChain

DETECTOR = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
HEADERS = {"User-Agent": "FaceChain-demo/1.0"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_crop(gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    crop = cv2.resize(gray[y:y+h, x:x+w], (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
    return ((crop - crop.mean()) / (crop.std() + 1e-6)).flatten()


def detect_and_encode(image_path: Path) -> np.ndarray:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = DETECTOR.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) != 1:
        raise ValueError(f"Expected exactly one face in {image_path}; found {len(faces)}")
    return encode_crop(gray, tuple(map(int, faces[0])))


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.sqrt(a.size))


def search_bluesky(query: str, limit: int) -> list[dict[str, Any]]:
    response = requests.get("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts", params={"q": query, "limit": limit}, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json().get("posts", [])


def post_url(post: dict[str, Any]) -> str:
    author = post.get("author", {}).get("handle", "unknown")
    return f"https://bsky.app/profile/{author}/post/{post.get('uri', '').rsplit('/', 1)[-1]}"


def image_urls(post: dict[str, Any]) -> list[str]:
    embed = post.get("record", {}).get("embed") or post.get("embed") or {}
    return [x.get("fullsize") or x.get("thumb") for x in embed.get("images", []) if x.get("fullsize") or x.get("thumb")]


def retrieve_image(url: str) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.content


def find_best(reference: Path, query: str, limit: int, threshold: float, workdir: Path) -> tuple[dict[str, Any], int, int]:
    reference_encoding = detect_and_encode(reference)
    posts = search_bluesky(query, limit)
    best: dict[str, Any] | None = None
    candidate_images = 0
    face_images = 0
    for post in posts:
        for url in image_urls(post):
            candidate_images += 1
            try:
                data = retrieve_image(url)
                path = workdir / ".candidate.jpg"
                path.write_bytes(data)
                image = cv2.imread(str(path))
                if image is None:
                    continue
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = DETECTOR.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
                if len(faces) == 0:
                    continue
                face_images += 1
                best_distance = min(distance(reference_encoding, encode_crop(gray, tuple(map(int, box)))) for box in faces)
                if best is None or best_distance < best["face_distance"]:
                    best = {"post": post, "image_url": url, "image_sha256": sha256_bytes(data), "face_distance": best_distance}
            except (requests.RequestException, ValueError, cv2.error) as exc:
                print(f"Skipping candidate media: {exc}", file=sys.stderr)
    if best is None or best["face_distance"] > threshold:
        actual = "none" if best is None else f"{best['face_distance']:.4f}"
        raise RuntimeError(f"No candidate passed the threshold. Searched {len(posts)} posts / {candidate_images} images; {face_images} contained faces; best distance={actual}. Increase --threshold only after validating consented demo data.")
    post = best["post"]
    return ({"source": "Bluesky public search API", "query": query, "posts_retrieved": len(posts), "candidate_images_retrieved": candidate_images, "face_images_checked": face_images, "post_url": post_url(post), "author_handle": post.get("author", {}).get("handle"), "text": post.get("record", {}).get("text", ""), "created_at": post.get("record", {}).get("createdAt"), "image_url": best["image_url"], "image_sha256": best["image_sha256"], "face_distance": best["face_distance"], "face_similarity": 1.0 / (1.0 + best["face_distance"]), "retrieved_at_unix": int(time.time())}, len(posts), candidate_images)


def main() -> int:
    parser = argparse.ArgumentParser(description="Consent-based face scan, genuine Bluesky search, and blockchain verification")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--query", required=True, help="Authorized public search query; this is not a hardcoded post")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--threshold", type=float, default=1.20)
    parser.add_argument("--chain", type=Path, default=Path("artifacts/chain.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/result.json"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.chain.parent.mkdir(parents=True, exist_ok=True)
    try:
        print("Face detected and encoded")
        print(f"Live search performed: query={args.query!r}, limit={args.limit}")
        record, posts, images = find_best(args.reference, args.query, args.limit, args.threshold, args.out.parent)
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"Candidates retrieved: {posts} posts / {images} images")
        print(f"Best matching post found: {record['post_url']}")
        print(f"Face distance={record['face_distance']:.4f}; similarity={record['face_similarity']:.4f}")
        print(f"Post fingerprint generated: {record['image_sha256']}")
        chain = LocalChain.load(args.chain)
        tx = chain.add_record(record)
        chain.save(args.chain)
        print(f"Blockchain transaction submitted: {tx['transaction_hash']}")
        on_chain = chain.get_fingerprint(tx["record_id"])
        print(f"On-chain fingerprint retrieved: {on_chain}")
        verified = chain.verify_record(tx["record_id"], record)
        print(f"Hashes compared: {'identical' if verified else 'different'}")
        print("✅ BLOCKCHAIN VERIFICATION PASSED" if verified else "❌ VERIFICATION FAILED / TAMPERED")
        return 0 if verified else 1
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"❌ PIPELINE FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
