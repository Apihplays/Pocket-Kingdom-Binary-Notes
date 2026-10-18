#!/usr/bin/env python3
"""Wrap a raw ARM code image into a minimal ELF32-ARM container.

Why: REA (and Ghidra/Hopper/IDA) cannot open a Symbian E32Image directly, so
`rea inspect-artifact 6RAH.APP` fails with "unsupported binary format" /
"provider_unavailable" for headerless raw binaries. Wrapping the extracted
text segment in an ELF32-ARM executable gives REA a container it accepts while
keeping the original virtual addresses, so every reported address matches the
game binary.

Usage:
    python3 tools/wrap_raw_arm_elf.py CODE.bin OUT.elf [--base 0x10000000]
                                                    [--symbol NAME=0xADDR ...]

Without --symbol the file has no symbol table; Hopper then discovers only the
entry point. Passing a handful of known function starts makes Hopper analyse
the whole image (thousands of procedures) and enables `rea decompile`,
`rea xrefs` and `rea instructions` on those functions.

Example:
    python3 tools/wrap_raw_arm_elf.py 6rah_code.bin /tmp/6rah.elf \
        --symbol merge_install=0x1000cc40 --symbol item_info=0x10031428
    npx rea-agents analyze /tmp/6rah.elf --provider hopper
    npx rea-agents xrefs /tmp/6rah.elf 0x1008fe2c --provider hopper
"""

from __future__ import annotations

import argparse
import struct

DEFAULT_SYMBOLS = {
    # Pocket Kingdom (6RAH.APP) function starts recovered during analysis.
    "sell_page_full": 0x10005DB4,
    "sell_confirm": 0x10005E98,
    "gold_credit": 0x10008BC4,
    "equipped_check": 0x100082E8,
    "merge_install": 0x1000CC40,
    "item_info": 0x10031428,
    "merge_ptr_init": 0x10069900,
}


def build_elf(code: bytes, base: int, symbols: dict[str, int]) -> bytes:
    text_off = 0x1000
    strtab = b"\x00"
    syms = [b"\x00" * 16]
    for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
        name_off = len(strtab)
        strtab += name.encode() + b"\x00"
        syms.append(struct.pack("<IIIBBH", name_off, addr, 0, 0x12, 0, 1))
    symtab = b"".join(syms)

    shstrtab = b"\x00.text\x00.symtab\x00.strtab\x00.shstrtab\x00"
    name_text, name_symtab, name_strtab, name_shstrtab = 1, 7, 15, 23

    symtab_off = text_off + len(code)
    strtab_off = symtab_off + len(symtab)
    shstrtab_off = strtab_off + len(strtab)
    shoff = (shstrtab_off + len(shstrtab) + 3) & ~3

    def sh(name, typ, flags, addr, off, size, link=0, info=0, align=4, entsize=0):
        return struct.pack(
            "<IIIIIIIIII", name, typ, flags, addr, off, size, link, info, align, entsize
        )

    sections = b"\x00" * 40
    sections += sh(name_text, 1, 0x6, base, text_off, len(code))
    sections += sh(name_symtab, 2, 0, 0, symtab_off, len(symtab), 3, 1, 4, 16)
    sections += sh(name_strtab, 3, 0, 0, strtab_off, len(strtab))
    sections += sh(name_shstrtab, 3, 0, 0, shstrtab_off, len(shstrtab))

    ehdr = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\x00" * 8 + struct.pack(
        "<HHIIIIIHHHHHH",
        2, 40, 1, base, 52, shoff, 0x05000000,  # ET_EXEC, EM_ARM, EF_ARM_EABI_VER5
        52, 32, 1, 40, 5, 4,
    )
    phdr = struct.pack(
        "<IIIIIIII", 1, text_off, base, base, len(code), len(code), 5, 0x1000
    )
    blob = ehdr + phdr
    blob += b"\x00" * (text_off - len(blob))
    blob += code + symtab + strtab + shstrtab
    blob += b"\x00" * (shoff - len(blob))
    return blob + sections


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw")
    ap.add_argument("elf")
    ap.add_argument("--base", default="0x10000000", help="load address of raw file")
    ap.add_argument(
        "--symbol",
        action="append",
        default=[],
        metavar="NAME=0xADDR",
        help="add a function symbol (repeatable)",
    )
    ap.add_argument(
        "--no-default-symbols", action="store_true", help="omit built-in symbols"
    )
    args = ap.parse_args()

    symbols = {} if args.no_default_symbols else dict(DEFAULT_SYMBOLS)
    for item in args.symbol:
        name, _, addr = item.partition("=")
        symbols[name] = int(addr, 16)

    code = open(args.raw, "rb").read()
    blob = build_elf(code, int(args.base, 16), symbols)
    with open(args.elf, "wb") as fh:
        fh.write(blob)
    print(
        f"wrote {args.elf}: {len(blob)} bytes, base {int(args.base,16):#x}, "
        f"code {len(code)} bytes, {len(symbols)} symbols"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
