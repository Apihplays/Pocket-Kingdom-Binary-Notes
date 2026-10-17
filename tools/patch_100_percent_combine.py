import os
import glob
import shutil

def patch_all_recipes_100_percent(app_dir: str = "System/Apps/6RAH"):
    """
    Patches ALL recipe tables in comp*.dat to 100% success rate:
    1. Standard recipes (comp00 - comp86): byte 22 = 100 (0x64)
    2. Multi-recipe tables (compa0 - compa6, comp92 - comp96):
       Every 16-byte recipe entry starting at offset 32 has its rate at offset + 6.
       We set every recipe rate byte to 100 (0x64).
    """
    files = sorted(glob.glob(os.path.join(app_dir, "comp*.dat")))
    total_patched = 0

    for fpath in files:
        with open(fpath, "rb") as f:
            data = bytearray(f.read())

        changed = False

        # Header rate (for standard 48-byte files)
        if len(data) >= 24 and data[22] > 0 and data[22] != 100:
            data[22] = 100
            changed = True

        # Multi-recipe entries (Emblems in compa0-compa6, high-tier recipes in comp92-comp96)
        # Each entry is 16 bytes starting at offset 32 (0x20)
        if len(data) >= 48:
            for off in range(32, len(data), 16):
                if off + 7 <= len(data):
                    rate = data[off + 6]
                    if 0 < rate <= 95:
                        data[off + 6] = 100
                        changed = True

        if changed:
            with open(fpath, "wb") as f:
                f.write(data)
            total_patched += 1

    print(f"Successfully patched {total_patched} recipe files including all emblem tables to 100%!")

def patch_itemdata_rates_100(app_dir: str = "System/Apps/6RAH"):
    """
    Patches the in-game recipe tables shipped inside itemdata.dat.

    The itemdata.dat tail is a byte-exact concatenation of the vanilla comp*.dat
    tables (the standalone comp*.dat files are never opened bygame code -
    verified: no filename reference anywhere in 6RAH.APP). In-game rates come
    from this tail, so the rates must be patched here:
    - Tier tables (comp00-comp86, comp92-comp96): header base rate u16 at +22.
    - Per-recipe rates: byte at +6 inside every 16-byte entry from +32
      (all families - tier tables ship 25/40/30/10/5% for unique recipes).
    Patched in both the base and english (localized) copies.
    """
    comp_files = sorted(glob.glob(os.path.join(app_dir, "comp*.dat")))
    sizes = [len(open(f, "rb").read()) for f in comp_files]
    blob_len = sum(sizes)
    patched = 0
    for stub, sub in [("", "itemdata.dat"), ("english/", "itemdata.dat")]:
        path = os.path.join(app_dir, stub, sub)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            data = bytearray(f.read())
        if len(data) < blob_len:
            print(f"Skipping {path}: too small for recipe tail")
            continue
        backup = path + ".orig"
        base = len(data) - blob_len
        changed = False
        for fpath, size in zip(comp_files, sizes):
            # Per-recipe success rate confirmed in-game: the byte at +6 of
            # every 16-byte entry (tier tables included - comp92-96 unique
            # bow recipes showed 25/40/40/30%). Header base rate at +22 too.
            for off in range(32, size - 6, 16):
                entry_rate = data[base + off + 6]
                if 0 < entry_rate < 100:
                    data[base + off + 6] = 100
                    changed = True
            if 0 < data[base + 22] < 100:
                # Table header base rate at +22.
                data[base + 22] = 100
                changed = True
            base += size
        if changed:
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            with open(path, "wb") as f:
                f.write(data)
            patched += 1
            print(f"Patched recipe rates in {path} to 100% (backup: {backup})")
    print(f"itemdata recipe tables patched: {patched} file(s)")



if __name__ == "__main__":
    patch_all_recipes_100_percent()
    patch_itemdata_rates_100()
