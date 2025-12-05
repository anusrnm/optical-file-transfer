import argparse, os
from file_transfer.core.manifest import build_manifest, save_manifest
from file_transfer.core.chunking import iter_file_chunks, DEFAULT_CHUNK_SIZE
from file_transfer.core.encoding_qr import manifest_to_qr_frames
from file_transfer.core.encoding_grid import encode_grid_frame, FRAME_PAYLOAD_SIZE
from file_transfer.core.fec import xor_parity

def write_qr_frames(manifest, out_dir):
    for idx, qr in manifest_to_qr_frames(manifest):
        fname = os.path.join(out_dir, f"bootstrap_qr_{idx}.png")
        if hasattr(qr, 'save'):
            qr.save(fname, scale=6)
        else:
            with open(fname + '.txt', 'wb') as f:
                f.write(qr)  # raw bytes fallback


def write_grid_frames(path, out_dir):
    frame_seq = 0
    with open(path, 'rb') as f:
        while True:
            data = f.read(FRAME_PAYLOAD_SIZE)
            if not data:
                break
            
            # Encode frame
            # Using frame_seq as chunk_idx for this transport-layer view
            img = encode_grid_frame(data, seq=frame_seq, chunk_idx=frame_seq)
            img.save(os.path.join(out_dir, f"frame_{frame_seq:05d}.png"))
            frame_seq += 1
            
    print(f"Generated {frame_seq} grid frames.")



def main():
    ap = argparse.ArgumentParser(description="Hybrid optical sender prototype")
    ap.add_argument('--input', required=True, help='File or folder to send')
    ap.add_argument('--out', required=True, help='Output directory for frames')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    manifest = build_manifest(args.input, chunk_size=FRAME_PAYLOAD_SIZE)
    save_manifest(manifest, os.path.join(args.out, 'manifest.json'))
    write_qr_frames(manifest, args.out)
    # For prototype: if input is a file, create grid frames; if folder, skip for now
    if os.path.isfile(args.input):
        write_grid_frames(args.input, args.out)
    print("Frames written to", args.out)

if __name__ == '__main__':
    main()
