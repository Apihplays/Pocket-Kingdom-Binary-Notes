import unittest
import os
import shutil
from tools.patch_mass_sell import patch_binary

class TestPatchMassSell(unittest.TestCase):
    def setUp(self):
        self.test_app = "System/Apps/6RAH/6RAH_test.APP"
        shutil.copy("System/Apps/6RAH/6RAH.APP", self.test_app)

    def tearDown(self):
        if os.path.exists(self.test_app):
            os.remove(self.test_app)
        if os.path.exists(self.test_app + ".orig"):
            os.remove(self.test_app + ".orig")

    def test_patch_binary_creates_backup_and_patches(self):
        res = patch_binary(self.test_app, self.test_app)
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(self.test_app + ".orig"))
        self.assertGreater(res["cave_size"], 64)
        self.assertGreaterEqual(res["cave_addr"], 0x10000000)

if __name__ == "__main__":
    unittest.main()
