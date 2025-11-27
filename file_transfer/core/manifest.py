import os, json, time, hashlib
from typing import List, Dict
from .chunking import collect_files, hash_file_sha256, DEFAULT_CHUNK_SIZE, build_merkle_leaves, merkle_root


def build_manifest(root: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Dict:
    files = collect_files(root)
    file_entries = []
    total_chunks = 0
    chunk_index_cursor = 0
    for fpath in files:
        size = os.path.getsize(fpath)
        # number of chunks for this file
        chunks = (size + chunk_size - 1) // chunk_size
        entry = {
            'path': os.path.relpath(fpath, root) if os.path.isdir(root) else os.path.basename(fpath),
            'size': size,
            'sha256': hash_file_sha256(fpath),
            'first_chunk': chunk_index_cursor,
            'chunk_count': chunks
        }
        file_entries.append(entry)
        chunk_index_cursor += chunks
        total_chunks += chunks
    leaves = build_merkle_leaves(files, chunk_size)
    root_hash = merkle_root(leaves)
    manifest = {
        'version': 1,
        'session_id': hashlib.sha256(str(time.time()).encode()).hexdigest()[:32],
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'files': file_entries,
        'chunk_size': chunk_size,
        'total_chunks': total_chunks,
        'merkle_root': root_hash,
        'encryption': {'enabled': False},
        'fec': {'scheme': 'parity', 'data': 8, 'parity': 1},
        'encoding': {'bootstrap': 'qr', 'data': 'grid'}
    }
    return manifest


def save_manifest(manifest: Dict, path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
