import argparse, os, json, glob
from file_transfer.core.decoding_grid import decode_grid_frame

def main():
    ap = argparse.ArgumentParser(description="Hybrid optical receiver prototype")
    ap.add_argument('--frames', required=True, help='Directory containing captured frames')
    ap.add_argument('--out', required=True, help='Output directory for reconstructed files')
    args = ap.parse_args()
    
    if not os.path.isdir(args.frames):
        raise SystemExit('Frames directory not found')
    
    os.makedirs(args.out, exist_ok=True)
    
    # 1. Try to load manifest (simulating QR decode)
    manifest_path = os.path.join(args.frames, 'manifest.json')
    manifest = None
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        print(f"Loaded manifest for session {manifest.get('session_id')}")
    
    # 2. Decode grid frames
    frame_files = sorted(glob.glob(os.path.join(args.frames, "frame_*.png")))
    if not frame_files:
        print("No grid frames found.")
        return

    received_chunks = {}
    
    print(f"Found {len(frame_files)} frames. Decoding...")
    
    for fp in frame_files:
        result = decode_grid_frame(fp)
        if result:
            header, payload = result
            seq = header['seq']
            received_chunks[seq] = payload
        else:
            print(f"Failed to decode {os.path.basename(fp)}")
            
    # 3. Reassemble
    sorted_seqs = sorted(received_chunks.keys())
    if not sorted_seqs:
        print("No valid data decoded.")
        return
        
    # Determine output filename
    out_filename = "reconstructed_file.bin"
    if manifest and manifest.get('files'):
        # Use the first file's name
        out_filename = manifest['files'][0]['path']
        
    out_path = os.path.join(args.out, out_filename)
    
    with open(out_path, 'wb') as f:
        for seq in sorted_seqs:
            f.write(received_chunks[seq])
            
    print(f"Reconstructed file saved to {out_path}")

if __name__ == '__main__':
    main()

