import os
import shutil
import struct
from typing import Dict, Any

def patch_binary(input_app: str, output_app: str) -> Dict[str, Any]:
    """
    Patches 6RAH.APP:
    1. In the page sell execution loop (0x100022f4 - 0x10002468):
       - At 0x100023EC: Change 'cmp r1, #0; beq #0x10002460' to NOPs.
         This forces the loop to execute the sell transaction on EVERY item on the screen
         instead of only the single cursor-selected item.
       - At 0x10002464: Change 'cmp r4, #3' to 'cmp r4, #4' so it covers all 5 rows (0..4).
    2. In the item stack quantity deductor (0x10005684):
       - At 0x100056A0..0x100056B4: Sell the full stack quantity (mov r2, r0)
         instead of a partial quantity.
    """
    backup_path = input_app + ".orig"
    if not os.path.exists(backup_path):
        shutil.copy2(input_app, backup_path)

    source_path = backup_path if os.path.exists(backup_path) else input_app

    with open(source_path, "rb") as f:
        data = bytearray(f.read())

    code_base = 0x10000000
    code_offset = 0x7C

    NOP = 0xE1A00000 # mov r0, r0

    # Patch 1: Bypass cursor filter at 0x100023EC and 0x100023F0
    # 0x100023ec: cmp r1, #0 -> NOP
    # 0x100023f0: beq #0x10002460 -> NOP
    off1 = code_offset + (0x100023EC - code_base)
    data[off1 : off1 + 8] = struct.pack("<2I", NOP, NOP)

    # Patch 2: Check up to 5 rows (0..4): cmp r4, #4 at 0x10002464
    off2 = code_offset + (0x10002464 - code_base)
    # cmp r4, #4 = 0xE3540004
    data[off2 : off2 + 4] = struct.pack("<I", 0xE3540004)

    # Patch 3: In 0x10005684, sell entire quantity r0:
    # 0x100056a0: mov r2, r0 (0xE1A02000)
    # 0x100056a4 .. 0x100056bc -> NOPs
    off3 = code_offset + (0x100056A0 - code_base)
    # 8 instructions from 0x100056a0 to 0x100056bc:
    # 1x mov r2, r0 + 7x NOP
    patch3_insns = [0xE1A02000] + [NOP] * 7
    data[off3 : off3 + 32] = struct.pack("<8I", *patch3_insns)

    with open(output_app, "wb") as f:
        f.write(data)

    return {
        "success": True,
        "backup_path": backup_path
    }

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "System/Apps/6RAH/6RAH.APP"
    res = patch_binary(target, target)
    print(f"Patched {target} successfully!")
    print(f"  Bypassed single-selection filter at 0x100023EC.")
    print(f"  Expanded visible item loop bound at 0x10002464 to 5 rows.")
    print(f"  Enabled full stack selling at 0x100056A0.")
    print(f"  Backup saved to: {res['backup_path']}")
