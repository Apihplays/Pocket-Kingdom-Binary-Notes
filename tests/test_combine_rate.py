import unittest
import glob
import os

class Test100PercentCombine(unittest.TestCase):
    def test_all_active_recipes_are_100_percent(self):
        files = sorted(glob.glob("System/Apps/6RAH/comp*.dat"))
        for fpath in files:
            with open(fpath, "rb") as f:
                d = f.read()
            if len(d) >= 24:
                rate = d[22]
                orig_path = fpath + ".orig"
                if os.path.exists(orig_path):
                    self.assertEqual(rate, 100, f"{fpath} should be 100% but is {rate}%")

if __name__ == "__main__":
    unittest.main()
