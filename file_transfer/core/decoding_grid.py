import struct
import zlib
from typing import Tuple, Optional
from PIL import Image
import math

PALETTE_4 = [(0,0,0),(255,255,255),(255,0,0),(0,255,0)]
HEADER_ROWS = 2
MAGIC = 0xABCD

def _color_dist(c1, c2):
    return sum((a-b)**2 for a,b in zip(c1, c2))

def _closest_symbol(color, palette):
    best_sym = 0
    min_dist = float('inf')
    for i, p in enumerate(palette):
        d = _color_dist(color, p)
        if d < min_dist:
            min_dist = d
            best_sym = i
    return best_sym

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

def decode_grid_image(img: Image.Image, grid_w: int = 64, grid_h: int = 36, bits_per_symbol: int = 2) -> Optional[Tuple[dict, bytes]]:
    img = img.convert('RGB')
    # Assume perfect alignment for now (reading generated file)
    
    width, height = img.size
    cell_w = width / grid_w
    cell_h = height / grid_h
    
    symbols = []
    for y in range(grid_h):
        for x in range(grid_w):
            # Sample center of cell
            px = int((x + 0.5) * cell_w)
            py = int((y + 0.5) * cell_h)
            # Clamp to bounds
            px = max(0, min(width-1, px))
            py = max(0, min(height-1, py))
            
            color = img.getpixel((px, py))
            sym = _closest_symbol(color, PALETTE_4)
            symbols.append(sym)
            
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
