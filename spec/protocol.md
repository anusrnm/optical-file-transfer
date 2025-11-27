# Hybrid Optical Transfer Protocol (Draft)

## 1. Goals
- Offline transfer via camera/display only.
- Handle arbitrarily large datasets (scalable chunking & resumable state).
- Adaptive throughput: start robust → escalate density.
- Integrity & optional confidentiality.

## 2. Terminology
- Session: A logical transfer instance identified by `session_id`.
- Chunk: Fixed-size slice of original file data (default 64 KiB draft).
- Frame: Visual representation of one or more chunks (plus FEC).
- FEC Group: Set of N data frames + M parity frames enabling recovery.

## 3. Manifest
```
{
  version: 1,
  session_id: <128-bit random>,
  created_utc: <iso8601>,
  files: [ {path, size, sha256, first_chunk, chunk_count}, ... ],
  chunk_size: 65536,
  total_chunks: <int>,
  merkle_root: <hex>,
  encryption: { enabled: bool, algo?: "AES-GCM"|"CHACHA20-POLY1305", nonce_len?: int },
  fec: { scheme: "parity"|"rs"|"fountain", data: N, parity: M },
  encoding: { bootstrap: "qr", data: "grid" }
}
```
Serialized as JSON (later: CBOR for efficiency) and sent via QR bootstrap frames.

## 4. Chunking
- Fixed size for all but final chunk.
- Merkle tree built over `sha256(chunk_data)` leaves.

## 5. Frame Header (Binary Layout Draft)
| Field | Bits | Notes |
|-------|------|-------|
| magic | 16 | 0xABCD |
| version | 4 | Protocol version |
| encoding_mode | 4 | 0=QR,1=GRID2,2=GRID3 etc. |
| session_id | 64 | Truncated from manifest 128-bit (could expand) |
| frame_seq | 32 | Monotonic |
| chunk_start | 32 | Index of first chunk in payload |
| chunk_count | 16 | Number of chunks carried |
| fec_group_id | 24 | Group for parity association |
| flags | 8 | bit 0=parity frame; bit1=encrypted; ... |
| header_crc | 16 | CRC16-CCITT |
Total: 16+4+4+64+32+32+16+24+8+16 = 216 bits (~27 bytes).

## 6. Encoding Modes
### 6.1 QR Bootstrap
- Each QR code holds part of manifest & session setup.
- Redundancy: Manifest may repeat across multiple QR frames (k copies).

### 6.2 Color Grid Data Frames
- Palette sizes: 4 colors (2 bits), 8 colors (3 bits), 16 (4 bits) dynamic.
- Symbol matrix example: 64 x 36 symbols (2304 symbols). At 3 bits → 6912 bits ≈ 864 bytes payload per frame minus header & FEC.
- Header region: top 2 rows reserved.

## 7. FEC Schemes
- Parity (XOR over data chunks) initial.
- Reed-Solomon over chunk symbols later (GF(256)).
- Fountain (RaptorQ) for very large sets (future).

## 8. Security
- Encrypt chunk payload prior to FEC (encrypt-then-FEC).
- AEAD tag verified after decoding & FEC recovery; failing frames discarded.
- Manifest may be optionally signed.

## 9. Resumability
- Receiver keeps bitmap of received chunk indices; can stop/restart.
- Sender repetition window: periodically re-emits missing sets (policy TBD).

## 10. Error Handling
- If header CRC fails: discard frame.
- If payload per-chunk hash mismatches Merkle leaf: request repeat (future two-way) or rely on periodic reissue.

## 11. Evolution
- Version increments permit new header fields; reserved bits kept for forward compatibility.

## 12. Open Questions
- Optimal symbol size vs camera resolution trade-off.
- Real-time color calibration model.
- Bootstrapping key exchange visually.

(End Draft)
