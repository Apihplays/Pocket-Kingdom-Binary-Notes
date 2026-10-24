#!/usr/bin/env python3
"""Make ``save.dat`` portable: pin the save cipher key to a fixed key.

Why: the game encrypts ``save.dat`` with Blowfish using 72 bytes of per-run game
state (``ctx+0x1b310``, filled at startup from an OS call). A save therefore only
decrypts on the install that wrote it — anywhere else the CRC check fails and the
game says "Save file is corrupted." (see ``notes/systems/save-file.md``).

The key schedule is ``0x10011038``: copy the standard P/S tables, XOR the caller's
72-byte key into P (an 18-iteration loop), then expand P and S by encrypting
zeros. This patch replaces the *first instruction of that XOR loop*
(``0x100110b4``, ``ldrb r4,[sl,r5]``) with an unconditional branch past the loop:

    before:  ldrb r4, [sl, r5]   ; loop body starts here (do-while)
    after:   b 0x10011128        ; straight to the P/S expansion

Result: the key never reaches the cipher, so every install — Windows, Linux,
Android — runs the same Blowfish with the all-zero key. Saves become freely
copyable between patched installs; the plaintext CRC-32 and the fixed 10584-byte
size are still checked, so real corruption is still reported.

Both the save path and the load path go through the same function (callers
``0x100750f8``, ``0x1007601c``, ``0x10077318``, ``0x100774a4``), so one patch
covers both directions.

Compatibility: saves written *before* this patch are encrypted with the real key
and will no longer load (back them up first — the game overwrites ``save.dat``).
Saves written by a patched install load on any other patched install of the same
game build.

Usage:
    python3 tools/patch_save_fixed_key.py [app_dir]
    python3 tools/patch_save_fixed_key.py --revert [app_dir]

Idempotent; keeps a one-time ``6RAH.APP.orig`` backup of the untouched binary.
"""

from __future__ import annotations

import os
import shutil
import sys

BASE = 0x10000000
CODE_OFF = 0x7C  # start of the text segment inside the E32 image

SITE_VA = 0x100110B4          # first instruction of the key-XOR loop
LOOP_EXIT_VA = 0x10011128     # P/S expansion begins here
ORIGINAL = bytes.fromhex("0540dae7")   # ldrb r4, [sl, r5]
PATCHED = bytes.fromhex("1b0000ea")    # b #0x10011128

# Bytes around the site that identify this exact build before we touch it.
# (VA: expected 4 bytes)
CONTEXT = {
    0x100110AC: bytes.fromhex("0060a0e3"),  # mov r6, #0
    0x100110B0: bytes.fromhex("0650a0e1"),  # mov r5, r6
    0x100110B4: ORIGINAL,                   # ldrb r4, [sl, r5]
    0x10011120: bytes.fromhex("110056e3"),  # cmp r6, #0x11
    0x10011124: bytes.fromhex("e2ffffda"),  # ble #0x100110b4
    0x10011128: bytes.fromhex("0030a0e3"),  # mov r3, #0
    0x100800B4: bytes.fromhex("886a3f24"),  # Blowfish P[0] = 0x243f6a88
    0x100800FC: bytes.fromhex("a60b31d1"),  # Blowfish S[0][0] = 0xd1310ba6
}


def _file_offset(va: int) -> int:
    return va - BASE + CODE_OFF


def _app_path(app_dir: str) -> str:
    return os.path.join(app_dir, "6RAH.APP")


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _state(data: bytes) -> str:
    """'patched', 'original', or 'unknown' for the binary at ``offset``."""
    site = _file_offset(SITE_VA)
    word = data[site:site + 4]
    if word == PATCHED:
        return "patched"
    if word == ORIGINAL:
        return "original"
    return "unknown"


def _context_ok(data: bytes) -> bool:
    for va, expected in CONTEXT.items():
        off = _file_offset(va)
        got = data[off:off + 4]
        if va == SITE_VA:
            if got not in (ORIGINAL, PATCHED):
                return False
        elif got != expected:
            return False
    return True


def patch_fixed_key(app_dir: str = "System/Apps/6RAH") -> bool:
    """Return True when the binary was changed by this call."""
    path = _app_path(app_dir)
    data = bytearray(_read(path))
    if not _context_ok(data):
        raise ValueError(
            f"{path}: unexpected bytes around 0x{SITE_VA:X} — not a known 6RAH build")
    state = _state(data)
    if state == "patched":
        print(f"{path}: already patched (fixed key)")
        return False
    if state != "original":
        raise ValueError(f"{path}: unrecognised bytes at 0x{SITE_VA:X}")
    backup = path + ".orig"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    elif _state(_read(backup)) != "original":
        raise ValueError(f"{backup}: backup is not the original binary — refusing to patch")
    site = _file_offset(SITE_VA)
    data[site:site + 4] = PATCHED
    with open(path, "wb") as f:
        f.write(data)
    print(f"{path}: key XOR loop skipped at 0x{SITE_VA:X} — saves now use the fixed key")
    return True


def revert_fixed_key(app_dir: str = "System/Apps/6RAH") -> bool:
    """Restore the original instruction (saves go back to the per-install key)."""
    path = _app_path(app_dir)
    data = bytearray(_read(path))
    if _state(data) != "patched":
        print(f"{path}: not patched — nothing to revert")
        return False
    site = _file_offset(SITE_VA)
    data[site:site + 4] = ORIGINAL
    with open(path, "wb") as f:
        f.write(data)
    print(f"{path}: restored the per-install key at 0x{SITE_VA:X}")
    return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    app_dir = args[0] if args else os.environ.get("PK_GAME_DIR", "System/Apps/6RAH")
    try:
        if "--revert" in sys.argv[1:]:
            revert_fixed_key(app_dir)
        else:
            patch_fixed_key(app_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
