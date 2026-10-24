import glob
import io
import contextlib
import os
import shutil
import tempfile
import unittest

from tests import assets

GAME_DIR = assets.GAME_DIR


def _comp_files(app_dir):
    return sorted(glob.glob(os.path.join(app_dir, "comp*.dat")))


def _rate_offsets(size):
    """Offsets of the success-rate fields in one table (header +22, entries +6)."""
    return [22] + [off + 6 for off in range(32, size - 6, 16)]


def _vanilla_itemdata(app_dir):
    """The pristine recipe blob: the .orig backup the 100% patch leaves behind."""
    for sub in ("", "english/"):
        path = os.path.join(app_dir, sub, "itemdata.dat.orig")
        if os.path.exists(path):
            return open(path, "rb").read()
    return None


class CombineRateTestCase(unittest.TestCase):
    """Runs the patch and revert tools on a temp install built from the vanilla
    reference, so results do not depend on whether the live install is patched."""

    def setUp(self):
        vanilla = _vanilla_itemdata(GAME_DIR)
        if vanilla is None:
            self.skipTest(f"no itemdata.dat.orig under {GAME_DIR!r}")
        sizes = {os.path.basename(p): os.path.getsize(p) for p in _comp_files(GAME_DIR)}
        tail = vanilla[len(vanilla) - sum(sizes.values()):]
        self.dir = tempfile.mkdtemp(prefix="pk-combine-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        os.makedirs(os.path.join(self.dir, "english"))
        self.vanilla_comps = {}
        base = 0
        for name, size in sizes.items():
            self.vanilla_comps[name] = tail[base:base + size]
            base += size
        self.vanilla = vanilla
        for name, blob in self.vanilla_comps.items():
            self.write(name, blob)
        for sub in ("", "english"):
            self.write(sub, "itemdata.dat", vanilla)
            self.write(sub, "itemdata.dat.orig", vanilla)

    def write(self, *parts):
        *name, blob = parts
        with open(os.path.join(self.dir, *name), "wb") as f:
            f.write(blob)

    def read(self, *parts):
        with open(os.path.join(self.dir, *parts), "rb") as f:
            return f.read()

    def run_patch(self):
        from tools.patch_100_percent_combine import (
            patch_all_recipes_100_percent, patch_itemdata_rates_100)
        with contextlib.redirect_stdout(io.StringIO()):
            patch_all_recipes_100_percent(self.dir)
            patch_itemdata_rates_100(self.dir)

    def run_revert(self):
        from tools.revert_combine_rates import (
            revert_comp_rates, revert_itemdata_rates)
        with contextlib.redirect_stdout(io.StringIO()):
            revert_comp_rates(self.dir)
            revert_itemdata_rates(self.dir)

    def test_patch_sets_all_rates_to_100(self):
        self.run_patch()
        for name, region in self.vanilla_comps.items():
            data = self.read(name)
            for off in _rate_offsets(len(region)):
                # 0 = "no header rate" (emblem tables); the patch leaves it 0.
                expected = 0 if region[off] == 0 else 100
                self.assertEqual(
                    data[off], expected,
                    f"{name} rate at {off} should be {expected}% but is {data[off]}%")
        blob_len = sum(len(r) for r in self.vanilla_comps.values())
        for sub in ("", "english"):
            data = self.read(sub, "itemdata.dat")
            base = len(data) - blob_len
            for name, region in self.vanilla_comps.items():
                for off in _rate_offsets(len(region)):
                    expected = 0 if region[off] == 0 else 100
                    self.assertEqual(
                        data[base + off], expected,
                        f"{sub}/itemdata.dat rate at {base + off} should be {expected}%")
                base += len(region)

    def test_revert_restores_vanilla_rates(self):
        self.run_patch()
        self.run_revert()
        self.assertEqual(self.read("itemdata.dat"), self.vanilla)
        self.assertEqual(self.read("english", "itemdata.dat"), self.vanilla)
        for name, region in self.vanilla_comps.items():
            self.assertEqual(self.read(name), region, name)

    def test_revert_restores_known_vanilla_values(self):
        self.run_patch()
        self.run_revert()
        expected = {  # verified vanilla rates (CLAUDE.md recipe-table layout)
            "comp00.dat": [80, 30],
            "comp06.dat": [50, 10],
            "comp86.dat": [50, 5],
            "comp93.dat": [65, 25, 40, 40],
            "compa0.dat": [0] + [90] * 9 + [80] * 4,
            "compa6.dat": [0, 40, 40, 40, 40, 40, 40, 30, 30, 30],
        }
        for name, rates in expected.items():
            data = self.read(name)
            self.assertEqual([data[o] for o in _rate_offsets(len(data))], rates, name)

    def test_revert_is_idempotent(self):
        self.run_patch()
        self.run_revert()
        once = {name: self.read(name) for name in self.vanilla_comps}
        once["itemdata"] = self.read("itemdata.dat")
        self.run_revert()
        self.assertEqual(self.read("itemdata.dat"), once["itemdata"])
        for name in self.vanilla_comps:
            self.assertEqual(self.read(name), once[name], name)

    def test_revert_leaves_other_bytes_alone(self):
        """Non-rate edits in the itemdata tail must survive a revert."""
        cooked = bytearray(self.read("itemdata.dat"))
        blob_len = sum(len(r) for r in self.vanilla_comps.values())
        marker = len(cooked) - blob_len + 40  # inside the first table, not a rate
        self.assertNotIn(marker, self._rate_positions(cooked))
        cooked[marker] = 0x2A
        self.write("itemdata.dat", bytes(cooked))
        self.run_revert()
        self.assertEqual(self.read("itemdata.dat")[marker], 0x2A)

    def _rate_positions(self, data):
        base = len(data) - sum(len(r) for r in self.vanilla_comps.values())
        positions = set()
        for region in self.vanilla_comps.values():
            for off in _rate_offsets(len(region)):
                positions.add(base + off)
            base += len(region)
        return positions


if __name__ == "__main__":
    unittest.main()
