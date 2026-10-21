---
id: effect-damage-reduction
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3d4  # battle-start jump table
  - 0x1000fa7c  # Phys Red 1 -> 0x10000
  - 0x1000fa90  # Phys Red 2 -> 0x20000
  - 0x1000faa4  # Phys Red 3 -> 0x40000
  - 0x1000fab8  # Magic Reduction + Magic Reflection -> 0x80000
  - 0x1000e7e4  # physical branch
  - 0x1000e77c  # magic branch
tags: [effect, combat, defense]
---

# Effects 35–39 — Physical / Magic reduction

> **TL;DR**
> - Physical Reduction 1/2/3: damage taken **×0.8 / ×0.6 / ×0.5**, highest tier only, min 1.
> - Magic Reduction (38): magic damage taken **×0.75**.
> - Magic Reflection (39) writes the **same bit** as 38 (`0x80000`) — it is a duplicate, there is
>   no reflect code.
> - All are passive: they are armed at battle start by dispatcher `0x1000f3a0`.

## Dispatch (battle start)

`0x1000f3a0(game, unit, id)` → `0x1000f3d4[id]`. Each handler only ORs one bit into the
unit's effect-flag word (`0x100081f0`):

| id | effect | bit |
|---|---|---|
| 35 | Physical Reduction 1 | `0x10000` |
| 36 | Physical Reduction 2 | `0x20000` |
| 37 | Physical Reduction 3 | `0x40000` |
| 38 | Magic Reduction | `0x80000` |
| 39 | Magic Reflection | `0x80000` (same handler) |

## Physical branch (`0x1000e7e4`)

Reached when the **attacker's** effect-flag bit `0x2` is clear (i.e. a physical hit). It tests
`0x70000` on the **defender** and applies exactly one tier — the highest set bit wins:

| flags | multiplier | code |
|---|---|---|
| `0x40000` (Phys Red 3) | ×0.5 | `dmg >> 1` |
| `0x20000` (Phys Red 2) | ×0.6 | `((0x66666667 * 3*dmg) >> 32) >> 1` |
| `0x10000` (Phys Red 1) | ×0.8 | `dmg − (((0x66666667 * dmg) >> 32) >> 1)` |

Then `max(1, dmg)` at `0x1000e8b0` and `0x10008af4(game, defender, dmg)`.

Stacking two tiers does **not** multiply the multipliers; the lower tier is ignored.

## Magic branch (`0x1000e77c`)

Reached when the attacker's effect bit `0x2` is set. If the defender has `0x80000`:

```
dmg = dmg - dmg/4        ; 75% taken
```

Clamped to at least 1 like the physical branch.

## Why 39 does nothing extra

`0x1000fab8` is shared by ids 38 and 39 and only sets `0x80000`. The reflect branch elsewhere
tests `0x8000`, but **no handler ever sets `0x8000`**. Magic Reflection is therefore just
Magic Reduction with a misleading name.

## Open questions
- Whether 38 and 39 were intended to be different in an earlier build. No code path sets the
  reflect bit, so there is nothing to test in-game.
