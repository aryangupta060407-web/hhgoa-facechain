import requests

response = requests.get(
    "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
    params={"q": "HH Goa", "limit": 1},
    headers={"User-Agent": "FaceChain-demo/1.0"},
    timeout=20,
)
response.raise_for_status()
posts = response.json().get("posts", [])
print("Bluesky API OK:", len(posts), posts[0].get("uri") if posts else "no-posts")
