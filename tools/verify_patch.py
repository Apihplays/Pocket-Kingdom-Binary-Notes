import struct
import capstone

def verify_patch(binary_path: str = "System/Apps/6RAH/6RAH.APP"):
    with open(binary_path, "rb") as f:
        data = f.read()

    code_base = 0x10000000
    code_offset = 0x7C

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)

    # 1. Verify 0x100023EC - 0x100023F0 are NOPs
    off1 = code_offset + (0x100023EC - code_base)
    dis1 = list(md.disasm(data[off1 : off1 + 8], 0x100023EC))
    for insn in dis1:
        print(f"[Verification] 0x{insn.address:x}: {insn.mnemonic} {insn.op_str}")
        assert insn.mnemonic == "mov" and insn.op_str == "r0, r0"

    # 2. Verify 0x10002464 is cmp r4, #4
    off2 = code_offset + (0x10002464 - code_base)
    dis2 = list(md.disasm(data[off2 : off2 + 4], 0x10002464))
    print(f"[Verification] 0x{dis2[0].address:x}: {dis2[0].mnemonic} {dis2[0].op_str}")
    assert dis2[0].mnemonic == "cmp" and dis2[0].op_str == "r4, #4"

    # 3. Verify 0x100056A0 is mov r2, r0
    off3 = code_offset + (0x100056A0 - code_base)
    dis3 = list(md.disasm(data[off3 : off3 + 4], 0x100056A0))
    print(f"[Verification] 0x{dis3[0].address:x}: {dis3[0].mnemonic} {dis3[0].op_str}")
    assert dis3[0].mnemonic == "mov" and dis3[0].op_str == "r2, r0"

    print("\nVerification successful: Page sell filter bypassed, 5-row loop enabled, full stack sell enabled.")

if __name__ == "__main__":
    verify_patch()
