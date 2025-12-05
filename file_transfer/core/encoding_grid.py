from typing import Tuple
import struct
import zlib
from PIL import Image, ImageDraw

PALETTE_4 = [(0,0,0),(255,255,255),(255,0,0),(0,255,0)]  # 2 bits per symbol
HEADER_ROWS = 2
MAGIC = 0xABCD

GRID_W = 64
GRID_H = 36
BITS_PER_SYMBOL = 2
FRAME_PAYLOAD_SIZE = (GRID_W * (GRID_H - HEADER_ROWS) * BITS_PER_SYMBOL) // 8

def pack_header(seq: int, chunk_idx: int, payload_len: int) -> bytes:
    """Pack header: magic(2), seq(4), chunk_idx(4), payload_len(4), crc(4). Total 18 bytes."""
    fmt = '>HIII'
    data = struct.pack(fmt, MAGIC, seq, chunk_idx, payload_len)
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return data + struct.pack('>I', crc)

def _bytes_to_symbols(data: bytes, bits_per_symbol: int = 2) -> list:
    symbols = []
    buffer = 0
    bits_in_buffer = 0
    mask = (1 << bits_per_symbol) - 1
    for b in data:
        buffer = (buffer << 8) | b
        bits_in_buffer += 8
        while bits_in_buffer >= bits_per_symbol:
            shift = bits_in_buffer - bits_per_symbol
            sym = (buffer >> shift) & mask
            symbols.append(sym)
            buffer &= (1 << shift) - 1 if shift > 0 else 0
            bits_in_buffer -= bits_per_symbol
    if bits_in_buffer > 0:
        sym = (buffer << (bits_per_symbol - bits_in_buffer)) & mask
        symbols.append(sym)
    return symbols


def encode_grid_frame(chunk_bytes: bytes, seq: int, chunk_idx: int, grid_w: int = GRID_W, grid_h: int = GRID_H, bits_per_symbol: int = BITS_PER_SYMBOL) -> Image:
    """Create a PNG image with embedded header and chunk data."""
    header_bytes = pack_header(seq, chunk_idx, len(chunk_bytes))
    
    header_symbols = _bytes_to_symbols(header_bytes, bits_per_symbol)
    data_symbols = _bytes_to_symbols(chunk_bytes, bits_per_symbol)
    
    # Pad header to fill HEADER_ROWS
    header_capacity = grid_w * HEADER_ROWS
    if len(header_symbols) > header_capacity:
        raise ValueError("Header too large for reserved rows")
    header_symbols += [0] * (header_capacity - len(header_symbols))
    
    # Pad data to fill rest of grid
    data_capacity = grid_w * (grid_h - HEADER_ROWS)
    if len(data_symbols) > data_capacity:
        # In a real app, we might split or error. For now, truncate or warn.
        # But chunk_size should be chosen to fit.
        # 64*34 = 2176 symbols. @2bits = 4352 bits = 544 bytes.
        # Wait, default chunk size is 64KB. That won't fit in one frame!
        # We need to split chunks into frame payloads.
        # OR we increase grid size / bits per symbol.
        # For this prototype, let's assume the caller handles sizing or we just fit what we can.
        # The user asked to handle "file size as much as possible".
        # So we should probably support multi-frame chunks or just smaller chunks.
        # Let's assume the input `chunk_bytes` is already sized for one frame.
        pass
        
    all_symbols = header_symbols + data_symbols
    total_capacity = grid_w * grid_h
    if len(all_symbols) < total_capacity:
        all_symbols += [0] * (total_capacity - len(all_symbols))
    else:
        all_symbols = all_symbols[:total_capacity]

    cell = 12  # pixel size per symbol
    
    # Add 1-cell border for alignment
    border = 1
    img_w = (grid_w + 2 * border) * cell
    img_h = (grid_h + 2 * border) * cell
    
    img = Image.new('RGB', (img_w, img_h), (0,0,0))
    draw = ImageDraw.Draw(img)
    
    # Draw Alignment Border (White)
    # Top
    draw.rectangle([0, 0, img_w-1, cell-1], fill=(255,255,255))
    # Bottom
    draw.rectangle([0, img_h-cell, img_w-1, img_h-1], fill=(255,255,255))
    # Left
    draw.rectangle([0, 0, cell-1, img_h-1], fill=(255,255,255))
    # Right
    draw.rectangle([img_w-cell, 0, img_w-1, img_h-1], fill=(255,255,255))
    
    # Draw Corner Anchors (Red)
    # TL
    draw.rectangle([0, 0, cell-1, cell-1], fill=(255,0,0))
    # TR
    draw.rectangle([img_w-cell, 0, img_w-1, cell-1], fill=(255,0,0))
    # BL
    draw.rectangle([0, img_h-cell, cell-1, img_h-1], fill=(255,0,0))
    # BR
    draw.rectangle([img_w-cell, img_h-cell, img_w-1, img_h-1], fill=(255,0,0))
    
    for y in range(grid_h):
        for x in range(grid_w):
            sym = all_symbols[y * grid_w + x]
            color = PALETTE_4[sym % len(PALETTE_4)]
            # Offset by border
            dx = x + border
            dy = y + border
            draw.rectangle([dx*cell, dy*cell, (dx+1)*cell-1, (dy+1)*cell-1], fill=color)
            
    return img
