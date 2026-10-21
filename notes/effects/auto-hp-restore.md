---
id: effect-auto-hp-restore
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3a0  # battle-start effect dispatcher
  - 0x1000f3d4  # battle-start jump table (index = id)
  - 0x1000f974  # Auto HP Restore 1 (id 24)
  - 0x1000f9b8  # Auto HP Restore 2 (id 25)
  - 0x1000f9fc  # Auto HP Restore 3 (id 26)
  - 0x10022230  # per-action update; ticks the timer at 0x10022384
  - 0x10022384  # regen tick body
  - 0x10008bc4  # heal, clamps to max HP
  - 0x100081f0  # OR into the effect-flag word
tags: [effect, combat, healing, timer]
---

# Effects 24/25/26 — Auto HP Restore 1 / 2 / 3

> **TL;DR**
> - Battle start ORs `0x1000000` / `0x2000000` / `0x4000000` into the unit's effect-flag word and
>   arms a **33-tick** timer.
> - Timer cell = `battle + 0x7a8 + 24*team + 4*slot`, where `battle = [ctx+0x1a590]`,
>   `team` = `[unit+0x7c]` (0 = the side in `ctx+0x498`, 1 = the other), `slot` = `[unit+0x78]`.
> - The timer decrements once per call of `0x10022230`; at 0 the unit is healed **2 / 5 / 10 HP**
>   (highest tier wins), clamped to max HP, then the timer resets to 33.
> - A floating message with id `0x41` (group `0xc1`) is shown on every heal.
> - The tick is skipped entirely while `ctx+0x44c != 0` or `[unit+0xe] & 4 != 0`.

## Dispatch (battle start)

`0x1000f3a0(ctx, unit, id)` → `0x1000f3d4[id]`; ids 24/25/26 land on `0x1000f974` /
`0x1000f9b8` / `0x1000f9fc`. The three handlers are identical except for the flag constant.

```
0x1000f974  ldr  r3, [pc, #0x38]      ; 0x1a590
0x1000f978  ldr  r1, [r7, r3]         ; battle = ctx->[0x1a590]
0x1000f97c  add  r2, r5, #0x78
0x1000f980  ldm  r2, {r2, r3}         ; r2 = slot, r3 = team
0x1000f984  add  r3, r3, r3, lsl #1   ; 3*team
0x1000f988  lsl  r3, r3, #3           ; 24*team
0x1000f98c  add  r3, r3, r2, lsl #2   ; + 4*slot
0x1000f990  add  r1, r1, #0x7a0
0x1000f994  add  r1, r1, #8           ; battle + 0x7a8
0x1000f998  mov  r2, #0x21
0x1000f99c  str  r2, [r1, r3]         ; timer = 33
0x1000f9a0  mov  r0, r7
0x1000f9a4  mov  r1, r5
0x1000f9a8  mov  r2, #0x1000000       ; id 24; 0x2000000 for 25, 0x4000000 for 26
0x1000f9ac  bl   #0x100081f0         ; effect_flags |= bit
```

`[unit+0x7c]` is written by `0x10021154`/`0x10021160` right after the battle-start dispatch
(`0x10021164`): `0` when `[unit+0x74] == ctx->[0x498]`, else `1`. So the array holds two teams ×
6 word slots (24 bytes each), starting at `battle+0x7a8`; the next timer array starts at
`battle+0x7d8`.

Both equipment effect slots are dispatched (`0x10021094` for `+0xc`, `0x100210f4` for `+0x10`),
so two copies of the same tier just re-arm the same bit/timer (no stacking).

## Tick

`0x10022230(game, unit)` is the per-unit update that every action handler calls on entry
(49 call sites, e.g. `0x10011808` from the handler at `0x100117f0`). Reaching `0x10022384`
requires:

- `0x10022240` `[unit+0xc] & 0xd0000 == 0` (no pending hit markers),
- `0x100222f4` `ctx+0x44c == 0`,
- `0x10022318` `[unit+0xe] & 4 == 0` (otherwise `0x10022320`–`0x10022380` services the
  *other* timer at `battle+0x7d8` and clears unit bit `0x40000` instead).

```
0x10022388  mov  r1, r4
0x1002238c  bl   #0x100082e8          ; effect_flags(unit)
0x10022390  tst  r0, #0x7000000
0x10022394  beq  #0x100224c8          ; no tier -> nothing to tick
...
0x100223bc  ldr  r2, [timer]
0x100223c0  sub  r2, r2, #1
0x100223c4  str  r2, [timer]
0x100223e8  ldr  r3, [timer]
0x100223ec  cmp  r3, #0
0x100223f0  bgt  #0x100224c8          ; still counting
```

At zero: message id `0x41` is queued (`0x10022434`–`0x10022444`, group `0xc1`), the timer is
rewritten with `0x21` (`0x10022460`–`0x1002246c`), then the heal amount is chosen:

```
0x1002247c  tst  r0, #0x4000000   ; tier 3
0x1002248c  mov  r2, #0xa         ; 10
0x100224a8  tst  r0, #0x2000000   ; tier 2
0x100224b4  mov  r2, #5
0x100224c0  mov  r2, #2           ; tier 1 / fallback
0x100224c4  bl   #0x10008bc4      ; heal(game, unit, amount)
```

Highest tier wins because the `0x4000000` test runs first; a unit with 25 + 26 heals 10.

## Why 33

33 ticks is roughly one action animation's worth of updates. The action handlers dispatch on
`[unit+0x70]` (anim state) and call `0x10022230` at the top of every invocation, so the timer
advances only while that unit is running an action — not on a global clock.

## Evidence

- Handlers: `0x1000f974` / `0x1000f9b8` / `0x1000f9fc`, all storing `0x21` at the same cell.
- Flags: `0x100081f0` is the OR-in helper; the same three bits are tested at `0x10022390`.
- Heal: `0x10008bc4` adds HP and clamps to `[unit+0x20]` (max HP) — see
  [battle records](../systems/battle-records.md).

## Open questions

- Is the 33-tick period exactly one action in practice? Not measured in-game; it depends on how
  many frames each action animation occupies.
- Should the tick also run while the unit is the defender? The `[unit+0xe] & 4` branch skips it;
  bit 4 is not yet mapped to a named state.
- `ctx+0x44c` (the other gate) is still unidentified.
