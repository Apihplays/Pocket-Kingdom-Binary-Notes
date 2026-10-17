import os
import glob
import shutil

def patch_combine_100_percent(app_dir: str = "System/Apps/6RAH"):
    """
    Sets the base combination success rate to 100% (0x64) in all comp*.dat files.
    Creates .orig backups of modified files.
    """
    files = sorted(glob.glob(os.path.join(app_dir, "comp*.dat")))
    patched = []

    for fpath in files:
        with open(fpath, "rb") as f:
            data = bytearray(f.read())

        if len(data) >= 24:
            # Offset 22 (0x16) stores the base success percentage
            cur_rate = data[22]
            if cur_rate > 0: # Only patch recipes that have an active success rate
                backup_path = fpath + ".orig"
                if not os.path.exists(backup_path):
                    shutil.copy2(fpath, backup_path)
                data[22] = 100 # 100%
                with open(fpath, "wb") as f:
                    f.write(data)
                patched.append((os.path.basename(fpath), cur_rate))

    print(f"Patched {len(patched)} combination recipe tables to 100% success rate:")
    for name, old in patched[:10]:
        print(f"  {name}: {old}% -> 100%")
    if len(patched) > 10:
        print(f"  ... and {len(patched) - 10} more.")

if __name__ == "__main__":
    patch_combine_100_percent()
