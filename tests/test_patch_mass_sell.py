import unittest
import os
import shutil
from tools.patch_mass_sell import patch_binary

class TestPatchMassSell(unittest.TestCase):
    def setUp(self):
        self.test_app = "System/Apps/6RAH/6RAH_test.APP"
        src = "System/Apps/6RAH/6RAH.APP.orig" if os.path.exists("System/Apps/6RAH/6RAH.APP.orig") else "System/Apps/6RAH/6RAH.APP"
        shutil.copy(src, self.test_app)

    def tearDown(self):
        if os.path.exists(self.test_app):
            os.remove(self.test_app)
        if os.path.exists(self.test_app + ".orig"):
            os.remove(self.test_app + ".orig")

    def test_patch_binary_creates_backup_and_patches(self):
        res = patch_binary(self.test_app, self.test_app)
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(self.test_app + ".orig"))
        self.assertEqual(res["hook_site_addr"], 0x10005E98)
        self.assertEqual(res["target_addr"], 0x10005DB4)

if __name__ == "__main__":
    unittest.main()
