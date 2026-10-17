import unittest
import os
from tools.find_code_cave import find_cave

class TestCodeCave(unittest.TestCase):
    def test_find_cave_returns_valid_address(self):
        # Use .orig if available to test cave discovery on clean binary
        binary = "System/Apps/6RAH/6RAH.APP.orig" if os.path.exists("System/Apps/6RAH/6RAH.APP.orig") else "System/Apps/6RAH/6RAH.APP"
        self.assertTrue(os.path.exists(binary))
        addr, size = find_cave(binary, min_size=64)
        self.assertGreaterEqual(addr, 0x10000000)
        self.assertLessEqual(addr, 0x100b0cac)
        self.assertGreaterEqual(size, 64)

if __name__ == "__main__":
    unittest.main()
