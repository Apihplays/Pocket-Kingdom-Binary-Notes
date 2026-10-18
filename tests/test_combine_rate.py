import unittest
import glob

class Test100PercentCombine(unittest.TestCase):
    def test_all_emblem_recipes_are_100_percent(self):
        # Verify compa0 through compa6
        for fpath in glob.glob("System/Apps/6RAH/compa*.dat"):
            with open(fpath, "rb") as f:
                d = f.read()
            for off in range(32, len(d), 16):
                rate = d[off + 6]
                self.assertEqual(rate, 100, f"{fpath} at offset {off+6} should be 100% but is {rate}%")

    def test_all_comp9_recipes_are_100_percent(self):
        for fpath in glob.glob("System/Apps/6RAH/comp9*.dat"):
            with open(fpath, "rb") as f:
                d = f.read()
            for off in range(32, len(d), 16):
                rate = d[off + 6]
                self.assertEqual(rate, 100, f"{fpath} at offset {off+6} should be 100% but is {rate}%")

    def test_itemdata_tier_header_rates_are_100_percent(self):
        # In-game rates live in the itemdata.dat tail (mirrors comp*.dat);
        # standalone comp files are never read by the game.
        import os
        from tools.patch_100_percent_combine import patch_itemdata_rates_100
        comp_sizes = [len(open(fp, "rb").read())
                      for fp in sorted(glob.glob("System/Apps/6RAH/comp*.dat"))]
        for sub in ["", "english/"]:
            path = "System/Apps/6RAH/" + sub + "itemdata.dat"
            with open(path, "rb") as f:
                d = f.read()
            base = len(d) - sum(comp_sizes)
            for size in comp_sizes:
                rate = d[base + 22]
                # emblem-style tables carry header rate 0; tier tables must be 100
                nonzero = rate != 0
                if nonzero:
                    self.assertEqual(
                        rate, 100,
                        f"{path} at {base+22} should be 100% but is {rate}%")
                base += size

    def test_itemdata_entry_rates_are_100_percent(self):
        # Per-recipe rate = byte at +6 of every 16-byte entry, ALL families
        # (tier tables ship 25/40/30/10/5% for unique recipes like bows).
        from tools.patch_100_percent_combine import patch_itemdata_rates_100
        comp_sizes = [len(open(fp, "rb").read())
                      for fp in sorted(glob.glob("System/Apps/6RAH/comp*.dat"))]
        for sub in ["", "english/"]:
            path = "System/Apps/6RAH/" + sub + "itemdata.dat"
            with open(path, "rb") as f:
                d = f.read()
            base = len(d) - sum(comp_sizes)
            for size in comp_sizes:
                for off in range(32, size - 6, 16):
                    rate = d[base + off + 6]
                    if rate != 0:
                        self.assertEqual(
                            rate, 100,
                            f"{path} entry rate at {base+off+6} should be 100% but is {rate}%")
                base += size

class TestItemdataPatchIdempotent(unittest.TestCase):
    def test_patch_runs_twice_without_growth(self):
        from tools.patch_100_percent_combine import patch_itemdata_rates_100
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            patch_itemdata_rates_100()
        s1 = open("System/Apps/6RAH/itemdata.dat","rb").read()
        with contextlib.redirect_stdout(buf):
            patch_itemdata_rates_100()
        s2 = open("System/Apps/6RAH/itemdata.dat","rb").read()
        self.assertEqual(s1, s2)

if __name__ == "__main__":
    unittest.main()
