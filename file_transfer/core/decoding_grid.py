import struct
import zlib
from typing import Tuple, Optional, List
from PIL import Image
import math
import numpy as np
import cv2

PALETTE_4 = [(0,0,0),(255,255,255),(255,0,0),(0,255,0)]
HEADER_ROWS = 2
MAGIC = 0xABCD

def _color_dist(c1, c2):
    return sum((a-b)**2 for a,b in zip(c1, c2))

def _refine_palette_and_decode(samples: List[Tuple[int, int, int]]) -> List[int]:
    """
    Uses K-Means-like approach to adapt the expected palette to the actual image colors.
    Initializes centroids with the ideal palette, then shifts them to match the data.
    """
    if not samples:
        return []
        
    data = np.array(samples, dtype=np.float32)
    
    # Init centroids with expected palette
    centroids = np.array(PALETTE_4, dtype=np.float32)
    
    # Run a few iterations of K-Means to adapt centroids
    # This handles lighting variations (e.g. gray instead of black, dim red)
    for _ in range(10):
        # Assign points to nearest centroid
        # dists shape: (N, 4)
        dists = np.linalg.norm(data[:, None] - centroids, axis=2)
        labels = np.argmin(dists, axis=1)
        
        # Update centroids
        new_centroids = centroids.copy()
        for i in range(4):
            mask = (labels == i)
            if np.any(mask):
                new_centroids[i] = data[mask].mean(axis=0)
        
        # Check convergence
        if np.allclose(centroids, new_centroids, atol=1.0):
            break
        centroids = new_centroids
        
    # Final assignment
    dists = np.linalg.norm(data[:, None] - centroids, axis=2)
    symbols = np.argmin(dists, axis=1)
    
    return symbols.tolist()

def _symbols_to_bytes(symbols: list, bits_per_symbol: int = 2) -> bytes:
    out = bytearray()
    buffer = 0
    bits_in_buffer = 0
    for sym in symbols:
        buffer = (buffer << bits_per_symbol) | sym
        bits_in_buffer += bits_per_symbol
        while bits_in_buffer >= 8:
            shift = bits_in_buffer - 8
            out.append((buffer >> shift) & 0xFF)
            bits_in_buffer -= 8
    return bytes(out)

def decode_grid_image(img: Image.Image, grid_w: int = 64, grid_h: int = 36, bits_per_symbol: int = 2, corners: List[Tuple[int, int]] = None) -> Optional[Tuple[dict, bytes]]:
    img = img.convert('RGB')
    
    # Perspective Correction if corners provided
    if corners and len(corners) == 4:
        # Convert PIL to OpenCV
        cv_img = np.array(img)
        cv_img = cv_img[:, :, ::-1].copy() # RGB to BGR
        
        # Source points (corners)
        src_pts = np.array(corners, dtype=np.float32)
        
        # Destination points (rectified)
        # We map to a fixed size that is a multiple of grid size for clean sampling
        # e.g. 10 pixels per cell
        cell_size = 10
        dst_w = grid_w * cell_size
        dst_h = grid_h * cell_size
        dst_pts = np.array([
            [0, 0],
            [dst_w, 0],
            [dst_w, dst_h],
            [0, dst_h]
        ], dtype=np.float32)
        
        # Warp
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(cv_img, M, (dst_w, dst_h))
        
        # Convert back to PIL for sampling loop (or just sample numpy)
        # Let's just sample numpy for speed
        img_arr = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
        
        width, height = dst_w, dst_h
        cell_w = cell_size
        cell_h = cell_size
        
        # Use the warped image array
        get_pixel = lambda x, y: img_arr[y, x]
        
    else:
        # Standard full-image sampling
        width, height = img.size
        
        # Detect border (encoder adds 1-cell border)
        # We use aspect ratio to guess if border is present, which is more robust than exact modulo check
        ratio = width / height
        ratio_border = (grid_w + 2) / (grid_h + 2)
        ratio_no_border = grid_w / grid_h
        
        # If closer to border ratio, or if exact match for border dimensions
        is_exact_border = (width % (grid_w + 2) == 0 and height % (grid_h + 2) == 0)
        is_closer_to_border = abs(ratio - ratio_border) < abs(ratio - ratio_no_border)
        
        if is_exact_border or is_closer_to_border:
            border = 1
            cell_w = width / (grid_w + 2)
            cell_h = height / (grid_h + 2)
        else:
            border = 0
            cell_w = width / grid_w
            cell_h = height / grid_h

        img_arr = np.array(img)
        get_pixel = lambda x, y: img_arr[y, x]
    
    samples = []
    for y in range(grid_h):
        for x in range(grid_w):
            # Sample center of cell
            px = int((x + border + 0.5) * cell_w)
            py = int((y + border + 0.5) * cell_h)
            # Clamp to bounds
            px = max(0, min(width-1, px))
            py = max(0, min(height-1, py))
            
            color = get_pixel(px, py)
            samples.append(color)
            
    # Adaptive decode
    symbols = _refine_palette_and_decode(samples)
            
    # Extract header symbols
    header_capacity = grid_w * HEADER_ROWS
    header_syms = symbols[:header_capacity]
    header_bytes = _symbols_to_bytes(header_syms, bits_per_symbol)
    
    # Parse header: magic(2), seq(4), chunk_idx(4), payload_len(4), crc(4) = 18 bytes
    if len(header_bytes) < 18:
        # print("Header too short")
        return None
        
    magic, seq, chunk_idx, payload_len = struct.unpack('>HIII', header_bytes[:14])
    stored_crc = struct.unpack('>I', header_bytes[14:18])[0]
    
    if magic != MAGIC:
        # print(f"Invalid magic: {hex(magic)}")
        return None
        
    calc_crc = zlib.crc32(header_bytes[:14]) & 0xFFFFFFFF
    if calc_crc != stored_crc:
        print("CRC mismatch")
        return None # Header corruption
        
    # Extract payload
    data_syms = symbols[header_capacity:]
    data_bytes = _symbols_to_bytes(data_syms, bits_per_symbol)
    
    if len(data_bytes) < payload_len:
        print(f"Payload truncated: got {len(data_bytes)}, expected {payload_len}")
        return None # Truncated
        
    payload = data_bytes[:payload_len]
    
    header_info = {
        'seq': seq,
        'chunk_idx': chunk_idx,
        'payload_len': payload_len
    }
    return header_info, payload

def decode_grid_frame(img_path: str, grid_w: int = 64, grid_h: int = 36, bits_per_symbol: int = 2) -> Optional[Tuple[dict, bytes]]:
    img = Image.open(img_path)
    return decode_grid_image(img, grid_w, grid_h, bits_per_symbol)
