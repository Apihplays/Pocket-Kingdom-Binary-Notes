---
id: effect-counter
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3d4  # battle-start jump table
  - 0x1000fa40  # Counter 1 -> bit 0x200000
  - 0x1000fa54  # Counter 2 -> bit 0x400000
  - 0x1000fa68  # Counter 3 -> bit 0x800000
  - 0x10022a70  # counter roll + range gate
  - 0x100228c4  # melee tick that calls it
tags: [effect, combat, counter]
---

# Effects 32/33/34 — Counter 1 / 2 / 3

> **TL;DR**
> - Chance to counter a melee hit: **20 % / 40 % / 60 %** for Counter 1 / 2 / 3.
> - Requires the attacker within **40 px in front** or **8 px behind** the unit.
> - On success the unit starts a counter exchange: `[unit+0x1c] = 2`, handler `0x100132ec`.
> - The three tiers stack their flags, but the roll picks the **highest** tier only
>   (`0x800000` → 60, else `0x400000` → 40, else 20).

## Dispatch (battle start)

`0x1000f3a0(game, unit, id)` → `0x1000f3d4[id]` → `0x1000fa40` / `0x1000fa54` / `0x1000fa68`.

Each handler does one `orr` into the unit's effect-flag word via `0x100081f0`:

| id | effect | bit |
|---|---|---|
| 32 | Counter 1 | `0x200000` |
| 33 | Counter 2 | `0x400000` |
| 34 | Counter 3 | `0x800000` |

Flags live at `battle+0x83c+4*slot` (player) / `+0x854+4*slot` (enemy);
read with `0x100082e8`, clear with `0x1000826c`.

## Roll (`0x10022a70`)

Called from the melee tick `0x100228c4`.

```
r0 = effect_flags(unit)
tst r0, #0xe00000        ; any counter tier?
beq  -> no counter
opponent = [unit+0x64]?  ; resolved attacker; must be non-zero
x = rand()%100           ; 0x100714e8, mod 100 inline
if flags & 0x800000: t = 60
elif flags & 0x400000: t = 40
else: t = 20
if x >= t -> fail
```

## Range gate

Uses facing bit `0x4` of `[unit+0xc]` and compares the opponent's x against the unit's x:

| facing bit | accepted opponent x |
|---|---|
| set (facing right) | `[x − 0x28, x + 8]` |
| clear (facing left) | `[x − 8, x + 0x28]` |

`0x28` = 40 px, `8` = 8 px. The y coordinate is not tested here — the melee tick already
guarantees adjacency.

## Result

```
success: [unit+0x70] = 2      ; anim state
         [unit+0x18] = 0      ; frame counter
         [unit+0x1c] = 2      ; action state = counter exchange
         -> 0x100132ec
failure: [unit+0x70] = 1
```

The counter itself is a normal attack action executed by the defender, so its damage uses the
defender's ATK vs the attacker's DEF and can itself roll effects (including a critical flag
left on the defender — see [critical.md](critical.md)).

## Open questions
- The counter action does not appear to clear `0x10000000` before resolving damage, so a
  crit mark left on the defender may double its counter damage. Not reproduced in-game.
