---
id: system-save-file
status: inferred
verified: 2026-10-24
addresses:
  - 0x10075e80  # save_load wrapper (builds path, checks file exists)
  - 0x10075f00  # save_load: reads 0x2958 bytes, decrypts, CRC-checks, fills ctx
  - 0x1007709c  # save_write: serialises ctx, appends CRC, encrypts, writes
  - 0x10011038  # Blowfish key schedule (18-word P + 4x256 S)
  - 0x100113c4  # encrypt buffer in place (8-byte blocks)
  - 0x10011600  # decrypt buffer in place (8-byte blocks)
  - 0x10074798  # copies the key descriptor ctx+0x1b310
  - 0x10077660  # delete save.dat / options.dat (reset)
  - 0x10077708  # open \System\Shareddata\101fd3dd.ini (create if missing)
  - 0x1006b754  # startup: fills ctx+0x1b310 from 0x1007d134
  - 0x1006cddc  # zero-fills 0x20 bytes at ctx+0x1b310
tags: [system, save, crypto]
---

# Save file — `save.dat` format, encryption and integrity check

> **TL;DR**
> - `C:\System\Apps\6RAH\save.dat` must be **exactly 10584 (`0x2958`) bytes**; the loader rejects
>   any other size before touching the contents (`0x10075f00`, compare at `0x10075f84`).
> - The body is **Blowfish, ECB, 8-byte blocks** (`0x10011038` key schedule, `0x100113c4`
>   encrypt, `0x10011600` decrypt). Tables: P = 18 words at `0x100800b4`, S = 4×256 at `0x100800fc`.
> - The plaintext ends with a **CRC-32 (poly `0x04C11DB7`, reflected = zlib)** of everything before
>   it; mismatch → "*Save file is corrupted. You must start from the beginning.*"
>   (`english/mestext.dat` records `0x14B`/`0x14C`/`0x14D`).
> - The key is **not stored in `save.dat`**: it is 72 bytes taken from the game context buffer
>   `ctx+0x1b310` (32 bytes, filled at startup from an OS call) — a raw copy is only readable
>   where that buffer matches.

## The two checks the loader performs

`0x10075e80` builds the path (`0x1007705c`) and calls `0x10075f00` when the file exists.

```
0x10075f3c  ldr r0,[pc]      ; 0x2970 = 10584 + 24
0x10075f40  bl  0x1007c184   ; allocate read buffer
0x10075f4c  blne 0x1007be94  ; zero it (0x2968 bytes)
0x10075f6c  bl  0x1007ce34   ; RFile::Read
0x10075f74  ldr r3,[r9]      ; descriptor length word
0x10075f78  bic r3,r3,#0xf0000000
0x10075f80  cmp r3,#0x2958   ; ***size must be exactly 10584***
0x10075f84  beq 0x10075fa8   ; ok -> decrypt path; else -> "corrupted"
```

CRC, from the load path (`0x1007602c`–`0x1007614c`):

- table built with polynomial `0x04C11DB7` through a bit-reversal helper (`0x1007d58c`), i.e. the
  ordinary reflected CRC-32 — `zlib.crc32` is the same function;
- running value starts `0xFFFFFFFF`, final `^0xFFFFFFFF`;
- covers `len-4` bytes, then four bytes are read little-endian and compared
  (`cmp r4, r5` at `0x1007613c`); any difference closes the file and shows message 331.

Both failures land on the same message box (`0x100105f0(..., 2)`), so "corrupted" means either
*size ≠ 0x2958* or *CRC mismatch* — the game cannot tell you which.

## Encryption

- Blowfish-ECB, 8-byte blocks, `len % 8 == 0` (10584 = 1323 blocks).
- Key schedule `0x10011038(ctx, keyptr, keylen)`:
  - copies the 18-word P array from `0x100800b4` and the 1024-word S table from `0x100800fc`;
  - XORs 18 big-endian key words (`0x48` = 72 bytes) into P, then the standard
    encrypt-zeros expansion of P and S. Verified against the standard Blowfish zero-key vector
    (`E(0,0) = 4ef997456198dd78`), so a plain Blowfish implementation reproduces it.
- Blocks are read/written as two little-endian `u32` per block (`0x100113c4` / `0x10011600`).
- Repeated 8-byte runs in the file (`a48080eef5df9ef7` ×186, `ec09a58a7a57a09a` ×157) are the
  same plaintext constant encrypted repeatedly — the signature of ECB mode.

## Where the key comes from

`0x10075fbc` copies the descriptor at `ctx+0x1b310` into a stack buffer, then
`0x10011038(state, ptr, len)` uses it as the key:

- `ctx+0x1b304` = `RFile`, `ctx+0x1b30c` = `RFs` for
  `\System\Shareddata\101fd3dd.ini` (`0x10077708`; the game creates the file when missing and
  writes a 4-byte value to it on save, `0x10077880`);
- `ctx+0x1b310` is a separate 32-byte buffer, zero-filled at init (`0x1006cddc`
  `Mem::FillZ(..., 0x20)`) and filled at startup by `0x1006b754` from the descriptor returned by
  the imported OS call at `0x1007d134` (copied by `0x1007c044`, source freed afterwards).

Because the key schedule always consumes 72 bytes, it reads the 32-byte buffer plus the 40 bytes
that follow it in the context.

## Portability patch — fixed key

`tools/patch_save_fixed_key.py` rewrites the first instruction of the key-XOR loop:

```
0x100110B4  ldrb r4, [sl, r5]   ; e7da4005  (loop body start, do-while)
     ->     b   0x10011128      ; ea00001b  (jump straight to the P/S expansion)
```

Zero iterations of the XOR loop leave P at the standard constants, so the expansion produces
Blowfish with a 72-byte all-zero key — identical on every install, independent of `ctx+0x1b310`
and of the `101fd3dd.ini` value. `0x10011038` has four callers, all in the save/load cluster
(`0x100750f8`, `0x1007601c`, `0x10077318`, `0x100774a4`), so one patch covers read and write.

The size check (`0x2958`) and the CRC-32 trailer are untouched, so genuine corruption is still
detected. Saves written by an unpatched install are still unreadable (their real key is lost).

## Open questions

- **What the `0x1007d134` value is** (32 bytes, per-run). Candidates: a device/system identity
  string, the app's private settings blob, or a value derived from the ROM. Not proven — the
  import ordinal could not be resolved (the E32 import directory in this image was not decoded).
- **Not yet decrypted:** the sample save used here (`save.dat`, 10584 bytes) did not decrypt with ~800 candidate keys (zero key, the 4-byte
  `101fd3dd.ini` value in several encodings, and every UTF-16/ASCII literal in `6RAH.APP`,
  padded and cycled, encrypt and decrypt). So the key derivation is still unknown, which is why
  this note is `inferred` rather than `verified`.
- Whether the two EKA2L1 installs (Windows host, Linux desktop) produce different `0x1007d134`
  values — the decisive in-game test: copy `save.dat` **and** the whole `data` / `SharedData`
  tree, then load with the emulator closed while copying.
- The fixed-key patch is byte-verified and unit-tested, but not yet run in EKA2L1: a save written
  by a patched install has not been round-tripped to a second patched install here.
