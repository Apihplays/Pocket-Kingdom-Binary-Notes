---
id: effect-resistances
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3a0  # battle-start dispatcher
  - 0x1000f3d4  # battle-start jump table (index = id, ids 0-43)
  - 0x1000f934  # Sleep Resistance (14) -> unit+0xc |= 0x4000
  - 0x1000f944  # Paralysis Resistance (17) -> unit+0xc |= 0x8000
  - 0x1000f954  # Poison Resistance (20) -> unit+0xc |= 0x1000
  - 0x1000f964  # Silence Resistance (23) -> unit+0xc |= 0x2000
  - 0x10007a50  # silence: ldrb unit+0xd, tst 0x20
  - 0x10007b3c  # poison:  ldrb unit+0xd, tst 0x10
  - 0x10007ca8  # deadly poison: same test as poison
  - 0x10007e14  # paralysis: ldrb unit+0xd, tst 0x80
  - 0x10007f5c  # sleep: ldrb unit+0xd, tst 0x40
  - 0x1000ee68  # attack-time table: 14/17/20/23 all point at 0x1000f390 (no-op)
tags: [effect, combat, status, resistance, immunity, battle-start]
---

# Effects 14/17/20/23 — Sleep / Paralysis / Poison / Silence Resistance

> **TL;DR**
> - These four are **battle-start only**. Each handler ORs one bit into the unit's state word at
>   `unit+0xc` and does nothing else.
> - 14 Sleep Resistance → `0x4000`, 17 Paralysis → `0x8000`, 20 Poison → `0x1000`,
>   23 Silence → `0x2000`.
> - Those word bits sit in byte `unit+0xd`, which is what the affliction routines read. If the
>   bit is set the routine shows message id `2` and returns — so resistance is **100 % immunity**,
>   not a reduced chance.
> - All four are **no-ops at attack time**: attack-table entries `0x1000ee68[13/16/19/22]` point at
>   the shared epilogue `0x1000f390`.
> - They grant nothing else: no stat bonus, no partial resist, no damage reduction.

## Why `+0xc` and `+0xd` are the same storage

`unit+0xc` is a 32-bit state word; `unit+0xd` is its second byte:

| word bit | byte `+0xd` bit |
|---|---|
| `0x1000` | `0x10` |
| `0x2000` | `0x20` |
| `0x4000` | `0x40` |
| `0x8000` | `0x80` |

So `ldrb r6,[unit,#0xd]; tst r6,#0x40` in the sleep routine is a test of word bit `0x4000`, which
is exactly what id 14 writes. This resolves the apparent contradiction between "resistance flags
are set at `[unit+0xc]`" and "the routine tests `[unit+0xd]`" — they are the same flag.

(The status-state bits used elsewhere, e.g. `unit+0xe` bit 1 = "took damage", are separate.)

## Handlers

```
0x1000f934  ldr  r3, [r5, #0xc]      ; 14 Sleep Resistance
0x1000f938  orr  r3, r3, #0x4000
0x1000f93c  str  r3, [r5, #0xc]
0x1000f940  b    #0x1000ff60         ; epilogue

0x1000f944  ldr  r3, [r5, #0xc]      ; 17 Paralysis Resistance
0x1000f948  orr  r3, r3, #0x8000
0x1000f94c  str  r3, [r5, #0xc]

0x1000f954  ldr  r3, [r5, #0xc]      ; 20 Poison Resistance
0x1000f958  orr  r3, r3, #0x1000
0x1000f95c  str  r3, [r5, #0xc]

0x1000f964  ldr  r3, [r5, #0xc]      ; 23 Silence Resistance
0x1000f968  orr  r3, r3, #0x2000
0x1000f96c  str  r3, [r5, #0xc]
```

`r5` is the unit in this dispatcher (it also reads `r5+0x74`/`r5+0x78` for side/slot in the
neighbouring handlers). Both equipment effect slots are dispatched, so a duplicated resistance
simply re-ORs the same bit.

## Consumption

Each affliction routine starts by testing the matching bit and bailing to a message with id `2`
before it touches the effect-flag word:

```
0x10007f5c  ldrb r6, [r4, #0xd]
0x10007f60  tst  r6, #0x40          ; sleep resistance
0x10007f64  beq  0x10007fb4         ; not resistant -> apply
            ; resistant: message id 2 at (x, y-0x14), then return
```

Identical structure at:

| ailment | routine | instruction | test |
|---|---|---|---|
| silence 21/22 | `0x10007a3c` | `0x10007a50` | `+0xd & 0x20` (word `0x2000`) |
| poison 18 | `0x10007b28` | `0x10007b3c` | `+0xd & 0x10` (word `0x1000`) |
| deadly poison 19 | `0x10007c94` | `0x10007ca8` | `+0xd & 0x10` (word `0x1000`) |
| paralysis 15/16 | `0x10007e00` | `0x10007e14` | `+0xd & 0x80` (word `0x8000`) |
| sleep 12/13 | `0x10007f48` | `0x10007f5c` | `+0xd & 0x40` (word `0x4000`) |

Consequences worth knowing when reading gear tables:

- Poison Resistance also blocks **Deadly Poison** (both routines share the `0x1000` test).
- Because the same bit is also the "already has this status" test, a resistant unit can never be
  afflicted, and there is no separate "immune" vs "already affected" state.
- There is no partial resistance and no saving throw anywhere in the four affliction routines; the
  only roll involved is the attack's accuracy check, which happens *before* the routines run.

## Attack-time no-ops

`0x1000ee68` (index = id-1) holds `0x1000f390` for entries 13, 16, 19 and 22 — the shared
epilogue. So equipping a resistance does not change the wearer's own attacks; 14/17/20/23 are
purely defensive battle-start bits.

## Evidence

- Table entries 14/17/20/23 → `0x1000f934` / `0x1000f944` / `0x1000f954` / `0x1000f964`
  in `0x1000f3d4`.
- Attack-table entries 13/16/19/22 → `0x1000f390` (epilogue) in `0x1000ee68`.
- `ldrb ...,[...,#0xd]` + `tst` pairs listed above; `+0xd` is the byte above `+0xc` in the
  [unit record](../systems/battle-records.md).

## Open questions

- Was the "also counts as already-affected" reuse intentional? It means a unit that somehow keeps
  a resistance flag after being afflicted cannot be re-afflicted, which is the desired outcome
  anyway.
- Are the four bits ever set by anything other than these handlers? A full-text scan of
  `[r,#0xd]` loads finds only the five affliction routines (plus two unrelated structs), and the
  only writers of `0x1000`/`0x2000`/`0x4000`/`0x8000` into `unit+0xc` are these handlers.
