from typing import Tuple
import hashlib
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
except ImportError:
    ChaCha20Poly1305 = None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encrypt_aead(key: bytes, plaintext: bytes, aad: bytes = b'') -> Tuple[bytes, bytes]:
    """Return (nonce, ciphertext_with_tag). Uses ChaCha20-Poly1305 if available."""
    if ChaCha20Poly1305 is None:
        raise RuntimeError('ChaCha20Poly1305 not available')
    nonce = hashlib.sha256(key + aad).digest()[:12]  # NOT secure random (prototype!)
    cipher = ChaCha20Poly1305(key)
    ct = cipher.encrypt(nonce, plaintext, aad)
    return nonce, ct


def decrypt_aead(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b'') -> bytes:
    if ChaCha20Poly1305 is None:
        raise RuntimeError('ChaCha20Poly1305 not available')
    cipher = ChaCha20Poly1305(key)
    return cipher.decrypt(nonce, ciphertext, aad)
