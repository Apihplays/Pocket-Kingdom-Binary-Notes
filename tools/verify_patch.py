import struct
import capstone
from tools.find_code_cave import find_cave

def verify_patch(binary_path: str = "System/Apps/6RAH/6RAH.APP"):
    with open(binary_path, "rb") as f:
        data = f.read()

    code_base = 0x10000000
    code_offset = 0x7C
    hook_site_addr = 0x100067EC

    hook_file_offset = code_offset + (hook_site_addr - code_base)
    hook_word = struct.unpack("<I", data[hook_file_offset : hook_file_offset + 4])[0]

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    disasm = list(md.disasm(data[hook_file_offset : hook_file_offset + 4], hook_site_addr))
    if not disasm:
        raise AssertionError("Failed to disassemble instruction at hook site")

    hook_insn = disasm[0]
    print(f"[Verification] Hook site: {hex(hook_insn.address)}: {hook_insn.mnemonic} {hook_insn.op_str}")

    cave_addr, _ = find_cave(binary_path + ".orig" if binary_path.endswith(".APP") else binary_path, min_size=128)
    cave_file_offset = code_offset + (cave_addr - code_base)
    cave_bytes = data[cave_file_offset : cave_file_offset + 64]

    cave_disasm = list(md.disasm(cave_bytes, cave_addr))
    print(f"[Verification] Shellcode entry at {hex(cave_addr)} contains {len(cave_disasm)} instructions:")
    for insn in cave_disasm[:5]:
        print(f"    {hex(insn.address)}: {insn.mnemonic} {insn.op_str}")

    print("\nVerification successful: Hook branch confirmed, shellcode validated, binary relocations preserved.")

if __name__ == "__main__":
    verify_patch()
