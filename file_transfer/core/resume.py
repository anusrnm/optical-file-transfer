import json, os
from typing import Set

class ResumeState:
    def __init__(self, path: str):
        self.path = path
        self.received: Set[int] = set()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r') as f:
                    data = json.load(f)
                    self.received = set(data.get('received', []))
            except Exception:
                self.received = set()

    def mark(self, chunk_index: int):
        self.received.add(chunk_index)

    def save(self):
        tmp = {'received': sorted(self.received)}
        with open(self.path, 'w') as f:
            json.dump(tmp, f)
