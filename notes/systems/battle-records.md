---
id: system-battle-records
status: verified
verified: 2026-10-21
addresses:
  - 0x100082e8  # effect-flag word getter
  - 0x100081f0  # effect-flag OR
  - 0x1000826c  # effect-flag clear
  - 0x100707a4  # roster lookup (id, slot, side)
  - 0x1006abd4  # side getter
  - 0x1006abdc  # slot getter
  - 0x1006abe4  # id getter
tags: [system, records, memory]
---

# Battle records — stats, units, effect flags

> **TL;DR**
> - Stats: **92-byte** records, player base `ctx+0x00`, enemy base `ctx+0x228`.
> - Live units: separate structs with side/slot/x/y and a state word at `+0xc`.
> - Per-unit effect flags: a second array, `ctx+0x83c+4*slot` (player) / `+0x854` (enemy).
> - Equipment: **52-byte** records, `ctx+0x4a8` (player) / `ctx+0x5e0` (enemy), effect ids at
>   `+0xc` and `+0x10`.

## Stat record (92-byte stride)

| offset | field | getter |
|---|---|---|
| `+0x00` | unit id | — |
| `+0x04` | HIT | `0x10008978` |
| `+0x14` | ATK | `0x10008490` |
| `+0x18` | DEF | `0x100084ec` |
| `+0x1c` | current HP | — |
| `+0x20` | max HP | — |
| `+0x24` | AGI | `0x100085a4` |
| `+0x28` | DEX | `0x10008714` |
| `+0x2c` | WIS | — (not isolated yet) |
| `+0x30` | INT | `0x10008600` |
| `+0x58` | status | — |

`0x10008548` is a *different* stat at `+0x34`, often mistaken for ATK — don't use it for damage.
Enemy copies are simply `+0x228` higher: e.g. enemy ATK = `ctx+0x23c`.

The stride is `23 * 4`; the code computes `slot * 23 << 2`.

## Unit struct

| offset | meaning |
|---|---|
| `+0x0c` | state bits (see below) |
| `+0x18` | frame counter |
| `+0x1c` | action state |
| `+0x3c` | timer |
| `+0x64` | last attacker slot |
| `+0x6c` | unit id |
| `+0x70` | anim state |
| `+0x74` | side |
| `+0x78` | slot |
| `+0x80` | x |
| `+0x84` | y |

### State bits at `+0x0c`

| bit | meaning |
|---|---|
| `0x4` | facing |
| `0x10000` | attacker hit marker |
| `0x40000` | defender hit marker |
| `0x400000` | counter exchange |
| `0x10000000` | transient critical (×2 damage) |
| `0xd0000` | blocks action |

The `0x10000000` here is **not** the same as `0x10000000` in the effect-flag word
(survive-fatal-blow). Different arrays.

## Effect-flag word

One 32-bit word per unit, parallel to the slots:

- get `0x100082e8(game, unit)` → `word`
- OR `0x100081f0(game, unit, bits)`
- clear `0x1000826c(game, unit, bits)`
- player base `ctx+0x83c`, enemy base `ctx+0x854`, `+4*slot`

Known bits:

| bit | effect |
|---|---|
| `0x2` | magic attack (on the attacker during damage) |
| `0x1` | halves HP Absorption drain (on the victim) |
| `0x10000/0x20000/0x40000` | Physical Reduction 1/2/3 |
| `0x80000` | Magic Reduction (and "Reflection" 39) |
| `0x200000/0x400000/0x800000` | Counter 1/2/3 |
| `0x1000000/0x2000000/0x4000000` | Auto HP Restore 1/2/3 |
| `0x10000000` | survive a fatal blow |
| `0x8000` | reflect bit — **never set** |

## Equipment records (52 bytes)

- player: `ctx+0x4a8 + 52*slot`
- enemy: `ctx+0x5e0 + 52*slot`
- `+0x00` item id (`0xff` = empty)
- `+0x0c` effect id #1
- `+0x10` effect id #2

The full item-definition table lives at `ctx+0x5e40` with the same 52-byte stride; an equipped
slot stores the item id and the two effect ids.

## Roster

`ctx+0x654` is the live-unit list. Lookup `0x100707a4(game, id, slot, side)` matches on
`0x1006abe4` (id), `0x1006abdc` (slot), `0x1006abd4` (side); `0xff` acts as a wildcard for
each. `0x1006abc4` returns position.

## Open questions
- `0x1000dfcc` filters roster entries with `[+0x6c] == 0xc0` (192). Since `[+0x6c]` is otherwise
  proven to be the unit id (units 7/8 checks at `0x1001f568`), 192 must be a transient marker or
  a second list shape. Not resolved.
