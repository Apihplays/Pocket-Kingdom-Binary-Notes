import struct
import capstone

def verify_patch(binary_path: str = "System/Apps/6RAH/6RAH.APP"):
    with open(binary_path, "rb") as f:
        data = f.read()

    code_base = 0x10000000
    code_offset = 0x7C
    hook_site_addr = 0x10005E98

    hook_file_offset = code_offset + (hook_site_addr - code_base)
    hook_bytes = data[hook_file_offset : hook_file_offset + 4]

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    disasm = list(md.disasm(hook_bytes, hook_site_addr))
    if not disasm:
        raise AssertionError("Failed to disassemble instruction at hook site")

    hook_insn = disasm[0]
    print(f"[Verification] Hook site: {hex(hook_insn.address)}: {hook_insn.mnemonic} {hook_insn.op_str}")

    if "#0x10005db4" not in hook_insn.op_str.lower():
        raise AssertionError(f"Expected branch to 0x10005db4, got: {hook_insn.op_str}")

    print("\nVerification successful: Single-sell execution correctly branches to multi-sell loop at 0x10005DB4.")

if __name__ == "__main__":
    verify_patch()
