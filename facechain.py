#!/usr/bin/env python3
"""Consent-based face matching -> Bluesky public-post search -> hash-chain anchoring."""
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

DETECTOR = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

from blockchain import LocalChain


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_and_encode(image_path: Path) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = DETECTOR.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        raise ValueError(f"No face detected in {image_path}")
    if len(faces) > 1:
        raise ValueError(f"Expected one face in {image_path}; found {len(faces)}")
    x, y, w, h = faces[0]
    crop = gray[y:y+h, x:x+w]
    crop = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
    crop = (crop - crop.mean()) / (crop.std() + 1e-6)
    return crop.flatten(), [tuple(map(int, f)) for f in faces]


def descriptor_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.sqrt(a.size))


def fetch_x_post(post_url: str) -> dict[str, Any]:
    post_id = post_url.rstrip('/').split('/')[-1].split('?')[0]
    response = requests.get(f"https://api.fxtwitter.com/status/{post_id}", headers={"User-Agent": "FaceChain-demo/1.0"}, timeout=30)
    response.raise_for_status()
    tweet = response.json().get("tweet", {})
    if not tweet:
        raise RuntimeError("X post could not be retrieved")
    return tweet


def search_bluesky(query: str, limit: int = 50) -> list[dict[str, Any]]:
    url = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
    response = requests.get(url, params={"q": query, "limit": limit}, timeout=30)
    response.raise_for_status()
    return response.json().get("posts", [])


def get_x_images(tweet: dict[str, Any]) -> list[tuple[bytes, str]]:
    results = []
    for media in tweet.get("media", {}).get("all", []):
        url = media.get("url") or media.get("thumbnail_url")
        if url:
            response = requests.get(url, headers={"User-Agent": "FaceChain-demo/1.0"}, timeout=30)
            response.raise_for_status()
            results.append((response.content, url))
    return results


def get_image_blob(post: dict[str, Any]) -> tuple[bytes, str] | None:
    embed = post.get("record", {}).get("embed") or post.get("embed") or {}
    if embed.get("$type") != "app.bsky.embed.images#view":
        return None
    images = embed.get("images", [])
    if not images:
        return None
    image_url = images[0].get("fullsize") or images[0].get("thumb")
    if not image_url:
        return None
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return response.content, image_url


def post_url(post: dict[str, Any]) -> str:
    author = post.get("author", {}).get("handle", "unknown")
    uri = post.get("uri", "")
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{author}/post/{rkey}"


def find_match(reference: Path, query: str | None, x_url: str | None, limit: int, threshold: float, workdir: Path) -> dict[str, Any]:
    reference_encoding, _ = detect_and_encode(reference)
    if x_url:
        tweet = fetch_x_post(x_url)
        candidates = [(tweet, data, url) for data, url in get_x_images(tweet)]
    else:
        candidates = []
        for post in search_bluesky(query or "", limit):
            downloaded = get_image_blob(post)
            if downloaded:
                candidates.append((post, downloaded[0], downloaded[1]))
    checked = 0
    for post, image_bytes, image_url in candidates:
        try:
            candidate_path = workdir / "candidate.jpg"
            candidate_path.write_bytes(image_bytes)
            image = cv2.imread(str(candidate_path))
            if image is None:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            locations = DETECTOR.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(locations) == 0:
                continue
            encodings = []
            for x, y, w, h in locations:
                crop = cv2.resize(gray[y:y+h, x:x+w], (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
                encodings.append(((crop - crop.mean()) / (crop.std() + 1e-6)).flatten())
            checked += 1
            best_distance = min(descriptor_distance(e, reference_encoding) for e in encodings)
            similarity = 1.0 / (1.0 + best_distance)
            if best_distance <= threshold:
                record = {
                    "source": "X public post retrieved through live API" if x_url else "Bluesky public search API",
                    "query": query,
                    "post_url": x_url or post_url(post),
                    "author_handle": post.get("author", {}).get("screen_name") if x_url else post.get("author", {}).get("handle"),
                    "text": post.get("text", "") if x_url else post.get("record", {}).get("text", ""),
                    "created_at": post.get("created_at") if x_url else post.get("record", {}).get("createdAt"),
                    "image_url": image_url,
                    "image_sha256": sha256_bytes(image_bytes),
                    "face_distance": best_distance,
                    "face_similarity": similarity,
                    "checked_face_images": checked,
                    "retrieved_at_unix": int(time.time()),
                }
                return record
        except (requests.RequestException, ValueError, cv2.error) as exc:
            print(f"Skipping candidate: {exc}", file=sys.stderr)
    raise RuntimeError(f"No matching face found in {len(candidates)} candidate media items ({checked} images contained faces). Try a broader query or higher --threshold.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Consent-based face scan, genuine Bluesky search, and blockchain verification")
    parser.add_argument("--reference", required=True, type=Path, help="One-face reference image; use only with subject consent")
    parser.add_argument("--query", help="Bluesky search query for the consented subject/topic")
    parser.add_argument("--x-url", help="Authorized public X post URL; retrieved live and searched across its media")
    parser.add_argument("--chain", type=Path, default=Path("artifacts/chain.json"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--threshold", type=float, default=1.20, help="normalized OpenCV descriptor distance threshold; lower is stricter")
    parser.add_argument("--out", type=Path, default=Path("artifacts/result.json"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.chain.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.parent / ".candidate.jpg"
    try:
        print(f"[1/3] Detecting and encoding one face from {args.reference}...")
        print(f"[2/3] Retrieving and searching authorized X post media: {args.x_url or args.query!r}")
        if not args.query and not args.x_url:
            parser.error("provide either --query or --x-url")
        record = find_match(args.reference, args.query, args.x_url, args.limit, args.threshold, args.out.parent)
        record.pop("checked_face_images", None)
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"    Found: {record['post_url']}")
        print(f"    Face distance: {record['face_distance']:.4f}")
        print("[3/3] Anchoring the discovered post fingerprint on the local tamper-evident chain...")
        chain = LocalChain.load(args.chain)
        tx = chain.add_record(record)
        chain.save(args.chain)
        verified = chain.verify_record(tx["record_id"], record)
        print(json.dumps({"record": record, "transaction": tx, "verified": verified}, indent=2))
        print(f"\nSUCCESS: blockchain verification = {verified}")
        return 0 if verified else 1
    finally:
        if temp.exists():
            temp.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
