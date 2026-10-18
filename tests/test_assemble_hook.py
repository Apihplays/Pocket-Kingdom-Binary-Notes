import unittest
import capstone
from tools.assemble_hook import generate_mass_sell_shellcode

class TestAssembleHook(unittest.TestCase):
    def test_shellcode_valid_arm_instructions(self):
        cave_addr = 0x100A0000
        return_addr = 0x10006804
        code = generate_mass_sell_shellcode(cave_addr=cave_addr, return_addr=return_addr)

        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        disasm = list(md.disasm(code, cave_addr))
        self.assertGreater(len(disasm), 10)

        mnemonics = [insn.mnemonic for insn in disasm]
        self.assertIn("cmp", mnemonics)
        self.assertIn("push", mnemonics)
        self.assertIn("pop", mnemonics)
        self.assertIn("bl", mnemonics)

if __name__ == "__main__":
    unittest.main()
