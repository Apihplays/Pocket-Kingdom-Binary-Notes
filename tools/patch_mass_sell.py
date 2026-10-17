import os
import shutil
import struct
from typing import Dict, Any
from tools.find_code_cave import find_cave
from tools.assemble_hook import generate_mass_sell_shellcode, arm_branch

def patch_binary(input_app: str, output_app: str) -> Dict[str, Any]:
    """
    Patches 6RAH.APP with the mass-sell hook.
    Creates a backup input_app.orig if not already present.
    """
    backup_path = input_app + ".orig"
    if not os.path.exists(backup_path):
        shutil.copy2(input_app, backup_path)

    # Search for cave in original clean backup if available
    search_target = backup_path if os.path.exists(backup_path) else input_app
    cave_addr, cave_size = find_cave(search_target, min_size=64)

    # Return address after single-item sell call (0x100067ec in 6RAH.APP)
    hook_site_addr = 0x100067EC
    return_addr = 0x100067F0

    shellcode = generate_mass_sell_shellcode(cave_addr=cave_addr, return_addr=return_addr)
    if len(shellcode) > cave_size:
        raise ValueError(f"Shellcode size {len(shellcode)} exceeds cave size {cave_size}")

    with open(input_app, "rb") as f:
        data = bytearray(f.read())

    code_base = 0x10000000
    code_offset = 0x7C

    # Write shellcode into the code cave
    cave_file_offset = code_offset + (cave_addr - code_base)
    data[cave_file_offset : cave_file_offset + len(shellcode)] = shellcode

    # Patch hook site: replace call at 0x100067EC with branch to shellcode
    hook_file_offset = code_offset + (hook_site_addr - code_base)
    hook_branch_insn = arm_branch(hook_site_addr, cave_addr, link=False)
    data[hook_file_offset : hook_file_offset + 4] = struct.pack("<I", hook_branch_insn)

    with open(output_app, "wb") as f:
        f.write(data)

    return {
        "success": True,
        "cave_addr": cave_addr,
        "cave_size": cave_size,
        "hook_site_addr": hook_site_addr,
        "shellcode_len": len(shellcode),
        "backup_path": backup_path
    }

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "System/Apps/6RAH/6RAH.APP"
    res = patch_binary(target, target)
    print(f"Patched {target} successfully!")
    print(f"  Cave Address: {hex(res['cave_addr'])}")
    print(f"  Hook Site: {hex(res['hook_site_addr'])}")
    print(f"  Backup saved to: {res['backup_path']}")
