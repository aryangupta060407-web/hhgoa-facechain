from pathlib import Path
from tempfile import TemporaryDirectory
from blockchain import LocalChain

with TemporaryDirectory() as d:
    path = Path(d) / 'chain.json'
    record = {'post_url': 'https://bsky.app/profile/demo/post/abc', 'image_sha256': '00' * 32}
    chain = LocalChain.load(path)
    tx = chain.add_record(record)
    chain.save(path)
    assert LocalChain.load(path).verify_record(tx['record_id'], record)
    altered = dict(record, post_url=record['post_url'] + '-altered')
    assert not LocalChain.load(path).verify_record(tx['record_id'], altered)
print('chain smoke test passed')
