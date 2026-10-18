import unittest
import os

from tests import assets
from tools.find_code_cave import find_cave


@assets.needs_game
class TestCodeCave(unittest.TestCase):
    def test_find_cave_returns_valid_address(self):
        # Use .orig if available to test cave discovery on clean binary
        binary = assets.app_binary()
        self.assertTrue(os.path.exists(binary))
        addr, size = find_cave(binary, min_size=64)
        self.assertGreaterEqual(addr, 0x10000000)
        self.assertLessEqual(addr, 0x100b0cac)
        self.assertGreaterEqual(size, 64)

if __name__ == "__main__":
    unittest.main()
