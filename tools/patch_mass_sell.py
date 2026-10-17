import os
import shutil
import struct
from typing import Dict, Any
from tools.find_code_cave import find_cave
from tools.assemble_hook import arm_branch

def patch_binary(input_app: str, output_app: str) -> Dict[str, Any]:
    """
    Patches 6RAH.APP with the mass-sell hook.
    Hooks the single-sell confirmation execution handler at 0x10005E98,
    redirecting it to the multi-item batch processor at 0x10005DB4.
    """
    backup_path = input_app + ".orig"
    if not os.path.exists(backup_path):
        shutil.copy2(input_app, backup_path)

    # Clean target
    source_path = backup_path if os.path.exists(backup_path) else input_app

    with open(source_path, "rb") as f:
        data = bytearray(f.read())

    code_base = 0x10000000
    code_offset = 0x7C

    # Hook site: 0x10005E98 is the entry of single-item sell execution.
    # 0x10005DB4 is the function that iterates all items 0..4 on the page
    # and sells each valid item via 0x10005E98.
    hook_site_addr = 0x10005E98
    target_multi_addr = 0x10005DB4

    hook_file_offset = code_offset + (hook_site_addr - code_base)
    # Branch directly from single-item sell handler to multi-item page processor:
    # b 0x10005DB4
    branch_opcode = arm_branch(hook_site_addr, target_multi_addr, link=False)
    data[hook_file_offset : hook_file_offset + 4] = struct.pack("<I", branch_opcode)

    with open(output_app, "wb") as f:
        f.write(data)

    return {
        "success": True,
        "hook_site_addr": hook_site_addr,
        "target_addr": target_multi_addr,
        "backup_path": backup_path
    }

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "System/Apps/6RAH/6RAH.APP"
    res = patch_binary(target, target)
    print(f"Patched {target} successfully!")
    print(f"  Hook Site: {hex(res['hook_site_addr'])} -> Branch to {hex(res['target_addr'])}")
    print(f"  Backup saved to: {res['backup_path']}")
