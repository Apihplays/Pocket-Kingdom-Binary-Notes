import struct
from typing import Tuple

def find_cave(binary_path: str, min_size: int = 128) -> Tuple[int, int]:
    """
    Scans the text segment of an E32 executable for a run of unused padding
    bytes (0x00) of at least min_size. Returns (memory_address, cave_size).
    """
    with open(binary_path, "rb") as f:
        data = f.read()

    # Symbian E32ImageHeader layout
    # TextSize at 0x60, CodeOffset at 0x64 (or 0x7c)
    # CodeBase is 0x10000000, CodeOffset is 0x7c
    code_base = 0x10000000
    code_offset = 0x7c
    text_size = struct.unpack("<I", data[0x60:0x64])[0]

    code_bytes = data[code_offset : code_offset + text_size]

    # Look for padding of 0x00 at 4-byte aligned boundary
    target_pattern = b"\x00" * min_size
    idx = 0
    best_offset = -1
    max_len = 0

    while True:
        pos = code_bytes.find(target_pattern, idx)
        if pos == -1:
            break
        # align to 4 bytes
        aligned_pos = (pos + 3) & ~3
        # calculate actual run length
        run_end = aligned_pos
        while run_end < len(code_bytes) and code_bytes[run_end] == 0:
            run_end += 1
        run_len = run_end - aligned_pos
        if run_len >= min_size and run_len > max_len:
            max_len = run_len
            best_offset = aligned_pos
        idx = pos + 1

    if best_offset == -1:
        raise RuntimeError(f"No code cave of size {min_size} found in {binary_path}")

    cave_memory_addr = code_base + best_offset
    return cave_memory_addr, max_len
