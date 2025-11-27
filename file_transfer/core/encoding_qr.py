import json
from typing import Dict, Iterator, Tuple

try:
    import segno
except ImportError:  # placeholder if dependency missing at runtime
    segno = None

MAX_QR_PAYLOAD = 2000  # conservative bytes for robustness


def manifest_to_qr_frames(manifest: Dict) -> Iterator[Tuple[int, 'segno.QRCode']]:
    """Split manifest JSON into multiple QR codes if needed."""
    data = json.dumps(manifest, separators=(',', ':')).encode('utf-8')
    for idx in range(0, len(data), MAX_QR_PAYLOAD):
        chunk = data[idx: idx + MAX_QR_PAYLOAD]
        if segno:
            qr = segno.make(chunk, micro=False)
        else:
            qr = chunk  # fallback raw bytes placeholder
        yield idx // MAX_QR_PAYLOAD, qr
