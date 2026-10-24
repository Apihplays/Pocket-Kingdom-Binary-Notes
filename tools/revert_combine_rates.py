#!/usr/bin/env python3
"""Restore the vanilla combine/craft success rates.

Undoes ``tools/patch_100_percent_combine.py``. The vanilla values come from the
``itemdata.dat.orig`` / ``english/itemdata.dat.orig`` backup the 100% patch made
before its first write, so this tool never guesses at the original numbers.

Reverted bytes (exactly the fields the 100% patch writes):
  * table header base rate at ``+22``
  * per-recipe rate at ``+6`` of every 16-byte entry from ``+32``

Only those rate bytes are touched, so unrelated edits (for example the
compa3/compa4 ingredient-id differences between the shipped ``comp*.dat`` dev
exports and the itemdata tail) survive. The standalone ``comp*.dat`` tables are
never opened by the game; their rates are restored from the same reference tail
because the 100% patch modified them too.

Usage:
    python3 tools/revert_combine_rates.py
    python3 tools/revert_combine_rates.py /path/to/System/Apps/6RAH

Idempotent: a second run makes zero changes and reports it.
"""

from __future__ import annotations

import glob
import os
import sys


def _comp_files(app_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(app_dir, "comp*.dat")))


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _comp_sizes(files: list[str]) -> list[int]:
    return [len(_read(f)) for f in files]


def _rate_offsets(size: int) -> list[int]:
    """Byte offsets of the success-rate fields inside one table."""
    return [22] + [off + 6 for off in range(32, size - 6, 16)]


def _vanilla_reference(app_dir: str) -> bytes:
    """The pristine recipe blob, taken from a backup made by the 100% patch."""
    for sub in ("", "english/"):
        path = os.path.join(app_dir, sub, "itemdata.dat.orig")
        if os.path.exists(path):
            return _read(path)
    raise FileNotFoundError(
        f"no itemdata.dat.orig in {app_dir!r} (or its english/ dir) — cannot "
        "tell vanilla rates without the pre-patch backup"
    )


def revert_itemdata_rates(app_dir: str = "System/Apps/6RAH") -> int:
    """Restore vanilla rate bytes in itemdata.dat + english/itemdata.dat."""
    files = _comp_files(app_dir)
    blob_len = sum(_comp_sizes(files))
    reverted = 0
    for sub in ("", "english/"):
        path = os.path.join(app_dir, sub, "itemdata.dat")
        backup = path + ".orig"
        if not os.path.exists(path):
            continue
        if not os.path.exists(backup):
            print(f"Skipping {path}: no .orig backup")
            continue
        data = bytearray(_read(path))
        ref = _read(backup)
        if len(data) != len(ref):
            print(f"Skipping {path}: size {len(data)} != backup size {len(ref)}")
            continue
        base = len(data) - blob_len
        changed = 0
        for size in _comp_sizes(files):
            for off in _rate_offsets(size):
                if data[base + off] != ref[base + off]:
                    data[base + off] = ref[base + off]
                    changed += 1
            base += size
        if changed:
            with open(path, "wb") as f:
                f.write(data)
            remaining = sum(1 for a, b in zip(data, ref) if a != b)
            print(f"Restored {changed} vanilla rate bytes in {path} "
                  f"({remaining} byte(s) still differ from the backup)")
            reverted += 1
        else:
            print(f"{path} already has vanilla rates")
    return reverted


def revert_comp_rates(app_dir: str = "System/Apps/6RAH") -> int:
    """Restore vanilla rate bytes in the standalone comp*.dat dev tables."""
    files = _comp_files(app_dir)
    if not files:
        return 0
    sizes = _comp_sizes(files)
    ref = _vanilla_reference(app_dir)
    base = len(ref) - sum(sizes)
    if base < 0:
        raise ValueError(f"{app_dir!r}: comp*.dat bigger than the itemdata backup")
    reverted = 0
    for path, size in zip(files, sizes):
        region = ref[base:base + size]
        base += size
        data = bytearray(_read(path))
        if len(data) != size or region[:4] != data[:4]:
            print(f"Skipping {path}: does not line up with the backup tail")
            continue
        changed = 0
        for off in _rate_offsets(size):
            if off < size and data[off] != region[off]:
                data[off] = region[off]
                changed += 1
        if changed:
            with open(path, "wb") as f:
                f.write(data)
            reverted += 1
    print(f"comp*.dat tables restored: {reverted} file(s) changed")
    return reverted


if __name__ == "__main__":
    app_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "PK_GAME_DIR", "System/Apps/6RAH")
    print(f"Reverting combine rates in: {app_dir}")
    try:
        revert_comp_rates(app_dir)
        revert_itemdata_rates(app_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
