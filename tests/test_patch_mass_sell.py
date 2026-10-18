import unittest
import os
import shutil

from tests import assets
from tools.patch_mass_sell import patch_binary


@assets.needs_game
class TestPatchMassSell(unittest.TestCase):
    def setUp(self):
        self.test_app = os.path.join(assets.GAME_DIR, "6RAH_test.APP")
        shutil.copy(assets.app_binary(), self.test_app)

    def tearDown(self):
        if os.path.exists(self.test_app):
            os.remove(self.test_app)
        if os.path.exists(self.test_app + ".orig"):
            os.remove(self.test_app + ".orig")

    def test_patch_binary_creates_backup_and_patches(self):
        res = patch_binary(self.test_app, self.test_app)
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(self.test_app + ".orig"))

if __name__ == "__main__":
    unittest.main()
