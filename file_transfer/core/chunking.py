import os
import hashlib
from typing import Iterator, Tuple, List

DEFAULT_CHUNK_SIZE = 65536  # 64 KiB

def iter_file_chunks(path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Iterator[Tuple[int, bytes]]:
    """Yield (offset_index, data) for the file at path.
    offset_index is the chunk index starting at 0.
    """
    with open(path, 'rb') as f:
        idx = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield idx, data
            idx += 1

def collect_files(root: str) -> List[str]:
    """Return a sorted list of file paths (recursively) or the single file if root is a file."""
    if os.path.isfile(root):
        return [root]
    paths = []
    for base, _dirs, files in os.walk(root):
        for fn in files:
            full = os.path.join(base, fn)
            paths.append(full)
    return sorted(paths)

def hash_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def build_merkle_leaves(file_paths: List[str], chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[str]:
    """Compute sha256 for each chunk as hex string (leaf). Heavy for huge sets; prototype only."""
    leaves = []
    for p in file_paths:
        for _idx, data in iter_file_chunks(p, chunk_size):
            leaves.append(hashlib.sha256(data).hexdigest())
    return leaves

def merkle_root(leaves: List[str]) -> str:
    """Compute a simple binary Merkle root from hex digest leaves."""
    if not leaves:
        return ''
    level = [bytes.fromhex(x) for x in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                pair = level[i] + level[i]  # duplicate last
            else:
                pair = level[i] + level[i+1]
            nxt.append(hashlib.sha256(pair).digest())
        level = nxt
    return level[0].hex()
