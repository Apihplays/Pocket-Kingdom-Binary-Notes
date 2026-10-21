---
id: effect-status-ailments
status: verified
verified: 2026-10-21
addresses:
  - 0x1000eda8  # attack-time dispatcher (r5 = victim, r8 = wielder)
  - 0x1000ee68  # attack-time jump table, index = id-1
  - 0x1000f2bc  # Sleep (12) hit-flag gate
  - 0x1000f2c8  # Sleep / Deep Sleep handler call
  - 0x1000f2d8  # Paralysis (15) hit-flag gate
  - 0x1000f2e4  # Paralysis handler call
  - 0x1000f2f4  # Poison (18) handler call
  - 0x1000f304  # Deadly Poison (19) handler call
  - 0x1000f314  # Silence (21) hit-flag gate
  - 0x1000f320  # Silence handler call
  - 0x10007f48  # Sleep / Deep Sleep
  - 0x10007e00  # Paralysis / Severe Paralysis
  - 0x10007b28  # Poison
  - 0x10007c94  # Deadly Poison
  - 0x10007a3c  # Silence / Strong Silence
  - 0x100081f0  # effect_flags |= bit
  - 0x100082e8  # effect_flags(unit)
  - 0x1000a5f8  # per-action natural cure roll
  - 0x10022214  # only caller of the cure roll
  - 0x10022d68  # "advance action unless paralysed"
  - 0x10022dc0  # "advance action unless asleep"
  - 0x1000e8f0  # poison damage tick (unreachable, see below)
tags: [effect, combat, status, ailment, sleep, poison, silence, paralysis]
---

# Effects 12/13/15/16/18/19/21/22 — Sleep, Paralysis, Poison, Silence

> **TL;DR**
> - All eight are **attack-time** effects: the wearer's equipped id is dispatched from table
>   `0x1000ee68[id-1]` by `0x1000eda8(game, victim, wielder, id)`.
> - 12 Sleep, 15 Paralysis, 21 Silence apply only when the attack's hit flag is set
>   (`[sp+0x10] == 0`, i.e. the accuracy roll succeeded).
> - 13 Deep Sleep, 16 Severe Paralysis, 22 Strong Silence call the **same routine** but skip the
>   hit test, so they land even on a miss. Poison (18) and Deadly Poison (19) also skip the test.
> - Status is a bit in the **effect-flag word**: silence `0x10`, poison `0x20`, deadly poison
>   `0x40`, sleep `0x100`, paralysis `0x400`.
> - Resistance (ids 14/17/20/23) is checked **first** from `unit+0xd`; if set, the routine shows
>   message id `2` and returns without applying anything — i.e. complete immunity.
> - Sleep and paralysis stall the action state machine; silence makes every magic ability handler
>   bail to action state 4 (the turn is wasted).
> - Each of the unit's actions ends with a natural-cure roll (`0x1000a5f8`): sleep / poison /
>   deadly poison are cured with `rand%100 < WIS/2`, silence / paralysis with
>   `rand%100 < INT/2`.
> - Poison damage is coded as 5 HP (18) / 10 HP (19) per action, **but the countdown it tests
>   (`battle+0x718`) is never armed** — the affliction writes `battle+0x748` instead. Treat
>   "poison deals no damage" as an inference (engine defect), not an in-game measurement.

## Dispatch

`0x1000eda8` computes the hit flag in `[sp+0x10]` (1 = miss, 0 = hit), then

```
0x1000ee54  ldr  sb, [sp, #0x14]      ; r3 = effect id
0x1000ee58  sub  r3, sb, #1
0x1000ee5c  cmp  r3, #0x1e            ; ids 1..31
0x1000ee60  ldrls pc, [pc, r3, lsl #2]
```

| id | name | entry | behaviour |
|---|---|---|---|
| 12 | Sleep | `0x1000f2bc` | `if [sp+0x10] != 0: return` → `0x10007f48` |
| 13 | Deep Sleep | `0x1000f2c8` | calls `0x10007f48` unconditionally |
| 15 | Paralysis | `0x1000f2d8` | hit-flag gate → `0x10007e00` |
| 16 | Severe Paralysis | `0x1000f2e4` | calls `0x10007e00` unconditionally |
| 18 | Poison | `0x1000f2f4` | calls `0x10007b28` unconditionally |
| 19 | Deadly Poison | `0x1000f304` | calls `0x10007c94` unconditionally |
| 21 | Silence | `0x1000f314` | hit-flag gate → `0x10007a3c` |
| 22 | Strong Silence | `0x1000f320` | calls `0x10007a3c` unconditionally |

`r5` is the victim and `r8` the wielder, per
[effect dispatch](../systems/effect-dispatch.md). The "strong" variants are therefore strictly
better: identical effect, no accuracy requirement.

## Common shape of the five routines

All five take `(game, unit)` and follow the same skeleton (sleep shown):

```
0x10007f48  push ...
0x10007f54  subs r4, r1, #0          ; unit
0x10007f58  beq  ret                 ; null-safe
0x10007f5c  ldrb r6, [r4, #0xd]      ; status/resistance byte
0x10007f60  tst  r6, #0x40           ; sleep resistance bit
0x10007f64  beq  apply
            ; resisted: queue message id 2 at (x, y-0x14), then return
0x10007fb4  ...
0x10007fbc  bl   0x100082e8          ; effect_flags(unit)
0x10007fc0  tst  r0, #0x100          ; already asleep?
0x10007fc4  bne  skip_popup          ; suppress duplicate popup
            ; popup: message 0x36 at (x, y-0x2d)
0x10008010  skip_popup:
0x10008018  mov  r2, #0x100
0x1000801c  bl   0x100081f0          ; effect_flags |= 0x100
0x10008020  mov  r3, #0xd
0x10008024  str  r3, [r4, #0x70]     ; anim state 0xd
0x10008028  bl   0x1006ad14
```

`unit+0xd` is **byte 1 of the state word at `unit+0xc`**, so a `tst` on `+0xd` bit `0x40` is a
test of word bit `0x4000`. That is exactly what the resistance handlers OR in (see
[resistances](resistances.md)). The same byte is also the "already afflicted" test, which is why
the resistance bits double as "immune".

| effect | routine | `+0xd` bit | word bit | effect-flag set | popup message |
|---|---|---|---|---|---|
| Sleep / Deep Sleep | `0x10007f48` | `0x40` | `0x4000` | `0x100` | `0x36` |
| Paralysis / Severe | `0x10007e00` | `0x80` | `0x8000` | `0x400` | `0x32` |
| Poison | `0x10007b28` | `0x10` | `0x1000` | `0x20` | `0x2f` then `0x31` |
| Deadly Poison | `0x10007c94` | `0x10` | `0x1000` | `0x40` | `0x2f` then `0x31` |
| Silence / Strong | `0x10007a3c` | `0x20` | `0x2000` | `0x10` | `0x2d` |

Name variants: `english/itemdata.dat` says *Deep Sleep*, *Severe Paralysis*, *Deadly Poison*,
*Strong Silence*; the compendium's crafting chart says *Deep Sleep*, *Severe Paralysis*,
**Severe Poison**, **Severe Silence**. Same four ids.

Notes on the routines:

- The three poison/paralysis/silence routines also OR `0x10000` into `unit+0xc` (attacker hit
  marker) before applying; sleep does not.
- The second `tst` is on the **effect-flag word**, not `unit+0xc`. For sleep it is the sleep bit
  itself (`0x100`); for the other three it is `0x1000`, a general "damage popup already shown"
  marker set by `0x100065d8`. Its only visible consequence is a suppressed popup — the status is
  still applied either way.
- Poison and deadly poison both write `0x28` (40) into
  `battle + 0x748 + 24*team + 4*slot`, with `team = [unit+0x7c]`, `slot = [unit+0x78]`
  (`0x10007c50`–`0x10007c78`, mirrored at `0x10007dbc`–`0x10007de4`). That cell is shared with the
  action-script delay helpers, not with the damage countdown (see below).
- Sleep and paralysis set `[unit+0x70] = 0xd` and call `0x1006ad14(unit)`. Silence returns
  immediately after setting the flag, without touching the animation state.

## What each status does

**Sleep (`0x100`)** — the action state machine helper `0x10022dc0` tests the bit and refuses to
advance (`moveq` only when clear), so a sleeping unit's action stalls. `0x1001d184` / `0x1001ec14`
clear `0x1100` (sleep + the popup marker) at action-state transitions.

**Paralysis (`0x400`)** — the twin helper `0x10022d68` does the same test for `0x400`. Both helpers
set `[unit+0x70] = 1` and call `0x1006ad14` when the bit is clear.

**Silence (`0x10`)** — every magic ability handler starts with
`bl 0x100082e8; tst r0,#0x10; bne <abort>`, and the abort branch sets action state 4
(`0x10011c10` → `0x10011d8c`, `0x1001cb18` → `0x1001cd9c`, and ~12 more). Physical ability
handlers do not test it. Silence therefore wastes any magic action but not a physical one.

**Poison (`0x20`) / Deadly Poison (`0x40`)** — the two ids set different bits, so they can coexist.
The end-of-action damage code at `0x1000e8f0` is selected by `tst r0,#0x60` and then
`tst r0,#0x20`: **5 HP** when the poison bit is set, **10 HP** otherwise (i.e. deadly only). With
both bits set the 5-damage branch wins.

## Natural cure

`0x1000a5f8(game, unit)` is called from exactly one place, `0x10022214`, at the tail of the
per-unit "action finished" handler:

```
0x1000a608  tst  r0, #0x570          ; any of silence/poison/deadly/sleep/paralysis
0x1000a60c  beq  ret
0x1000a61c  tst  r0, #0x410          ; silence (0x10) or paralysis (0x400)
0x1000a620  beq  0x1000a66c
            ; rng = rand() % 100; r0 = INT(unit)/2
0x1000a658  cmp  r4, r0, asr #1      ; r4 = rng
0x1000a65c  movlt r0, r5
0x1000a660  movlt r1, r6
0x1000a664  movlt r2, #0x410
0x1000a668  bllt 0x1000826c          ; clear 0x410
0x1000a678  tst  r0, #0x160          ; sleep (0x100) / deadly (0x40) / poison (0x20)
...
0x1000a6b4  cmp  r4, r0, asr #1      ; r0 = WIS(unit)/2
0x1000a6b8  bge  ret
0x1000a6c8  bl   0x1000826c          ; clear 0x160
```

So per action: **silence and paralysis are cured with `rand%100 < INT/2`**, and **sleep, poison and
deadly poison with `rand%100 < WIS/2`**. `rand()` is `0x100714e8` (17-bit). At 20 INT that is 10 %
per action; at 200 INT it is guaranteed.

Poison's 40-tick cell (`battle+0x748`) is not a poison timer in practice: the action helpers
`0x10022b90` / `0x10022c98` set that cell to `0x21` (33) on entry, decrement it, and on zero clear
effect bits `0x1000` / `0x2000` respectively — not `0x20` / `0x40`.

## Poison damage defect

The damage branch lives at the end of `0x1000dfcc(game, defender)` (the hit resolver called from
`0x10022230`), after the per-target loop:

```
0x1000e8f0  tst  r0, #0x60
0x1000e8f4  beq  ret
0x1000e914  add  r1, r1, #0x710
0x1000e918  add  r1, r1, #8          ; battle + 0x718
0x1000e91c  ldr  r2, [r1, r3]
0x1000e920  sub  r2, r2, #1
0x1000e924  str  r2, [r1, r3]
0x1000e948  ldr  r3, [r3, r1]
0x1000e94c  cmp  r3, #0
0x1000e950  bne  ret                 ; only fires when the counter is exactly 0
0x1000e954  add  r2, r0, #0x740
0x1000e958  add  r2, r2, #8          ; writes battle + 0x748
0x1000e95c  mov  r3, #0x28
0x1000e960  str  r3, [r2, r1]        ; re-arm 40 ... on the wrong table
0x1000e970  tst  r0, #0x20
0x1000e978  mov  r2, #5              ; poison
0x1000e98c  mov  r2, #0xa            ; deadly poison
0x1000e998  bl   0x10008af4          ; subtract HP
```

`battle+0x718` is zeroed at battle init (`0x10069914`, loop over 2 teams × 6 slots, stride 24) and
is only ever *decremented*, here. `0`, then `-1`, then `-2` … never returns to `0`, so the damage
branch is unreachable as written. The affliction routines write `0x28` into `battle+0x748`
(`0x10007c78`, `0x10007dd8`), one 48-byte table later — apparently a wrong-offset bug of the same
family as the DEF setter bug documented in
[stat modifiers](stat-modifiers.md#engine-defect-57911-are-all-def).

I have **not** measured poison damage in-game; this section is an instruction-level inference.
Everything above it (bits, immunity, cure maths, action stalls, silence gate) is proven by the
listed addresses.

## Evidence

- Attack table entries and gates: `0x1000f2bc`–`0x1000f32c`.
- Routines: `0x10007a3c` (silence), `0x10007b28` (poison), `0x10007c94` (deadly),
  `0x10007e00` (paralysis), `0x10007f48` (sleep).
- Flag ORs: `0x10007b10` (`0x10`), `0x10007c4c` (`0x20`), `0x10007db8` (`0x40`),
  `0x10007f20` (`0x400`), `0x1000801c` (`0x100`).
- Immunity reads: `ldrb rX,[unit,#0xd]` at `0x10007a50`, `0x10007b3c`, `0x10007ca8`,
  `0x10007e14`, `0x10007f5c`.
- Cure: `0x1000a5f8`, caller `0x10022214`.
- Action stalls: `0x10022d68` / `0x10022dc0`.
- Silence abort: `0x10011c10` → `0x10011d8c` sets `[unit+0x70] = 4`.

## Open questions

- Poison damage: does the retail game really never tick? Needs an in-game test (poison a unit,
  pass several turns, watch HP). The counter mismatch is unambiguous in code.
- Is `battle+0x718` ever written by a code path that builds the address dynamically
  (no `#0x718` literal exists anywhere in the text segment)? Not found.
- Message texts for ids `2`, `0x2d`, `0x2f`, `0x31`, `0x32`, `0x36` were not located in
  `battlemes.dat` (that file holds the Spanish win quotes); they live in another message table.
- Whether the "strong" variants were meant to have a longer duration: the code sets no timer for
  any of the three, so no.
