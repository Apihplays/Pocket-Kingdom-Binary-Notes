import os
import shutil
import tempfile
import unittest

from tests import assets

GAME_DIR = assets.GAME_DIR
APP = assets.APP

SITE_FILE_OFF = 0x100110B4 - 0x10000000 + 0x7C
PATCHED = bytes.fromhex("1b0000ea")   # b #0x10011128


@assets.needs_game
class TestFixedSaveKeyPatch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pk-app-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "6RAH.APP")
        shutil.copy2(APP, self.path)
        # tests must start from the pristine binary, not from a patched install
        backup = APP + ".orig"
        if os.path.exists(backup) and os.path.getsize(backup) == os.path.getsize(APP):
            shutil.copy2(backup, self.path)
        from tools.patch_save_fixed_key import revert_fixed_key
        revert_fixed_key(self.dir)
        self.original = self.read()

    def read(self, path=None):
        with open(path or self.path, "rb") as f:
            return f.read()

    def bytes_at_site(self):
        return self.read()[SITE_FILE_OFF:SITE_FILE_OFF + 4]

    def test_patch_skips_the_key_loop(self):
        from tools.patch_save_fixed_key import patch_fixed_key
        self.assertTrue(patch_fixed_key(self.dir))
        self.assertEqual(self.bytes_at_site(), PATCHED)
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        ins = list(md.disasm(PATCHED, 0x100110B4))[0]
        self.assertEqual(ins.mnemonic, "b")
        self.assertEqual(ins.op_str, "#0x10011128")  # jump target = P/S expansion

    def test_only_four_bytes_change(self):
        from tools.patch_save_fixed_key import patch_fixed_key
        patch_fixed_key(self.dir)
        patched = self.read()
        self.assertEqual(len(patched), len(self.original))
        diff = [i for i in range(len(patched)) if patched[i] != self.original[i]]
        self.assertEqual(diff, list(range(SITE_FILE_OFF, SITE_FILE_OFF + 4)))

    def test_patch_is_idempotent(self):
        from tools.patch_save_fixed_key import patch_fixed_key
        patch_fixed_key(self.dir)
        once = self.read()
        self.assertFalse(patch_fixed_key(self.dir))
        self.assertEqual(self.read(), once)

    def test_backup_is_the_original(self):
        from tools.patch_save_fixed_key import patch_fixed_key
        patch_fixed_key(self.dir)
        backup = self.read(self.path + ".orig")
        self.assertEqual(backup, self.original)

    def test_revert_restores_the_per_install_key(self):
        from tools.patch_save_fixed_key import patch_fixed_key, revert_fixed_key
        patch_fixed_key(self.dir)
        self.assertTrue(revert_fixed_key(self.dir))
        self.assertEqual(self.read(), self.original)

    def test_refuses_a_build_it_does_not_know(self):
        from tools.patch_save_fixed_key import patch_fixed_key
        data = bytearray(self.read())
        data[SITE_FILE_OFF:SITE_FILE_OFF + 4] = b"\x00\x00\x00\x00"
        with open(self.path, "wb") as f:
            f.write(data)
        with self.assertRaises(ValueError):
            patch_fixed_key(self.dir)
        self.assertEqual(self.bytes_at_site(), b"\x00\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
