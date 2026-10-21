---
id: effect-stat-modifiers
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3a0  # battle-start dispatcher (Up, ids 0-11 even)
  - 0x1000f3d4  # battle-start jump table
  - 0x1000eda8  # attack-time dispatcher (Down, ids 1-11 odd)
  - 0x1000ee68  # attack-time jump table (index = id-1)
  - 0x1000f484  # ATK Up
  - 0x1000f54c  # DEF Up
  - 0x1000f614  # AGI Up
  - 0x1000f6dc  # DEX Up
  - 0x1000f7a4  # INT Up
  - 0x1000f86c  # WIS Up
  - 0x1000eee4  # ATK Down
  - 0x1000efb8  # DEF Down
  - 0x1000f044  # AGI Down  } all four share
  - 0x1000f0d0  # DEX Down  } the tail at
  - 0x1000f15c  # INT Down  } 0x1000f26c
  - 0x1000f1e8  # WIS Down  }
  - 0x1000f26c  # shared Down tail (applies DEF)
tags: [effect, combat, stats, buff, debuff, bug]
---

# Effects 0–11 — ATK/DEF/AGI/DEX/INT/WIS Up & Down

> **TL;DR**
> - **Up** (0/2/4/6/8/10) runs at battle start: the wearer's stat becomes `stat + stat/4`
>   (**+25 %**, integer truncation). Two copies compound to ×1.5625.
> - **Down** (1/3/5/7/9/11) runs on a landing attack: it subtracts `INT(target)/4` from the
>   **wearer's own** stat. The target is never modified.
> - `ATK Down` writes ATK and `DEF Down` writes DEF. The other four (`AGI/DEX/INT/WIS Down`)
>   fall into the same tail and therefore also write **DEF** — the AGI/DEX/INT/WIS setters are
>   only ever called by their *Up* handlers. Engine defect, reachable via Griffon/Ninja/Vampire/
>   Lich Blood.
> - Up has no gate; Down requires the dispatcher's hit flag `[sp+0x10] == 0`.

## Dispatch

| id | effect | table | handler |
|---|---|---|---|
| 0 | ATK Up | `0x1000f3d4` | `0x1000f484` |
| 2 | DEF Up | `0x1000f3d4` | `0x1000f54c` |
| 4 | AGI Up | `0x1000f3d4` | `0x1000f614` |
| 6 | DEX Up | `0x1000f3d4` | `0x1000f6dc` |
| 8 | INT Up | `0x1000f3d4` | `0x1000f7a4` |
| 10 | WIS Up | `0x1000f3d4` | `0x1000f86c` |
| 1 | ATK Down | `0x1000ee68[0]` | `0x1000eee4` |
| 3 | DEF Down | `0x1000ee68[2]` | `0x1000efb8` |
| 5 | AGI Down | `0x1000ee68[4]` | `0x1000f044` |
| 7 | DEX Down | `0x1000ee68[6]` | `0x1000f0d0` |
| 9 | INT Down | `0x1000ee68[8]` | `0x1000f15c` |
| 11 | WIS Down | `0x1000ee68[10]` | `0x1000f1e8` |

The battle-start table entries for the odd ids point at `0x1000ff60` (no-op), so **Down never
fires at battle start**. Conversely the attack table entries for the even ids point at
`0x1000f390` (return), so **Up never fires on attack**.

## Up — +25 % at battle start

ATK Up in full (`0x1000f518`–`0x1000f544`):

```
0x1000f518  mov  r0, r7
0x1000f51c  mov  r1, r5
0x1000f520  bl   #0x10008490      ; r0 = ATK(unit)
0x1000f524  add  r3, r0, #3
0x1000f528  cmp  r0, #0
0x1000f52c  asrge r6, r0, #2      ; amount = stat/4 (truncate toward 0)
0x1000f530  asrlt r6, r3, #2
0x1000f534  mov  r0, r7
0x1000f538  mov  r1, r5
0x1000f53c  rsb  r2, r6, #0       ; -amount
0x1000f540  bl   #0x10009304      ; setter
```

The setter subtracts its argument:

```
0x10009340  ldr  r3, [r1, r2]
0x10009344  rsb  r3, r4, r3       ; r3 = r3 - r4
0x10009348  str  r3, [r1, r2]
```

So passing `-stat/4` yields `stat + stat/4`. Stat 100 → 125; stat 10 → 12 (10 + 2).

Getters and setters, with the stat-record field each setter writes:

| stat | getter | setter | field | record offset |
|---|---|---|---|---|
| ATK | `0x10008490` | `0x10009304` | `+0x14` | `0x23c` |
| DEF | `0x100084ec` | `0x100093d0` | `+0x18` | `0x240` |
| AGI | `0x100085a4` | `0x10009700` | `+0x24` | `0x24c` |
| DEX | `0x10008714` | `0x10009634` | `+0x28` | `0x250` |
| WIS | `0x100086b8` | `0x10009568` | `+0x2c` | `0x254` |
| INT | `0x10008600` | `0x1000949c` | `+0x30` | `0x258` |

The setters branch on `[unit+0x74] == ctx->[0x498]` to pick the player base (`+0x14…`) or the
enemy base (`+0x228 + field`, e.g. `0x23c`).

Each Up handler also queues two floating messages (group `0xc1`, `0x1006d544`): the stat-specific
id, then `0x1f` (31, the generic "UP" label).

| Up | first msg | Down | first msg |
|---|---|---|---|
| ATK | `0x12` (18) | ATK | `6` |
| DEF | `0x14` (20) | DEF | `8` |
| INT | `0x16` (22) | INT | `0x0a` (10) |
| WIS | `0x18` (24) | WIS | `0x0c` (12) |
| DEX | `0x1a` (26) | DEX | `0x0e` (14) |
| AGI | `0x1c` (28) | AGI | `0x10` (16) |

Down's second message is `0x1e` (30, "DOWN").

Both equipment effect slots are dispatched at battle start (`0x10021094` for `+0xc`,
`0x100210f4` for `+0x10`). Because each handler re-reads the *current* stat, two ATK Up copies
give 125 → 156 (×1.5625), not 150.

The buff is written straight into the live stat record, so it lasts the whole battle and has no
timer.

## Down — self-debuff on hit

ATK Down (`0x1000eee4`) checks the hit flag first, then shows messages 6 / 30, then:

```
0x1000ef84  mov  r0, r7
0x1000ef88  mov  r1, r5
0x1000ef8c  bl   #0x10008600      ; r0 = INT(target)
0x1000ef90  add  r3, r0, #3
0x1000ef94  cmp  r0, #0
0x1000ef98  asrge r6, r0, #2      ; amount = INT(target)/4
0x1000ef9c  asrlt r6, r3, #2
0x1000efa0  mov  r0, r7
0x1000efa4  mov  r1, r8          ; <-- the WIELDER, not r5
0x1000efa8  mov  r2, r6          ; positive amount
0x1000efac  bl   #0x10009304      ; ATK(wielder) -= amount
```

`r5` = victim and `r8` = wielder in `0x1000eda8`; this is the same convention that makes
HP Absorption (ids 27/28) heal `r8` and damage `r5`. Since the attack-time caller
`0x1000ec44` passes the *attacker's* equipped ids, every Down proc degrades the attacker.

DEF Down (`0x1000efb8`) builds messages 8 / 30 and branches to the shared tail `0x1000f26c`:

```
0x1000f288  mov  r0, r7
0x1000f28c  mov  r1, r5
0x1000f290  bl   #0x10008600      ; INT(target)
0x1000f2a4  mov  r0, r7
0x1000f2a8  mov  r1, r8
0x1000f2ac  mov  r2, r6
0x1000f2b0  bl   #0x100093d0      ; DEF(wielder) -= amount
0x1000f2b4  b    #0x1000f390
```

AGI/DEX/INT/WIS Down (`0x1000f044` / `0x1000f0d0` / `0x1000f15c` / `0x1000f1e8`) also branch to
`0x1000f26c` after their own messages, so they run the **same DEF write**. The callers of the six
setters prove no other path exists:

```
0x10009304 (ATK) <- 0x1000efac (ATK Down), 0x1000f540 (ATK Up)
0x100093d0 (DEF) <- 0x1000f2b0 (shared Down tail), 0x1000f608 (DEF Up)
0x1000949c (INT) <- 0x1000f860 (INT Up) only
0x10009568 (WIS) <- 0x1000f928 (WIS Up) only
0x10009634 (DEX) <- 0x1000f798 (DEX Up) only
0x10009700 (AGI) <- 0x1000f6d0 (AGI Up) only
```

## Quirks

- The Down debuff never touches the target, despite the name. Each landing hit removes another
  `INT(target)/4` from the wielder, with no cap and no timer.
- `AGI/DEX/INT/WIS Down` lower DEF. The message text still says AGI/DEX/INT/WIS, so the display
  and the stat change disagree.
- The amount uses the **target's INT**, so a high-INT enemy makes the wearer's debuff worse.
- Down procs need `[sp+0x10] == 0` (successful hit). Unlike Critical, they do test the flag.

## Evidence

- Table words are absolute addresses; `0x1000ee68` index = `id-1`, `0x1000f3d4` index = `id`.
- `0x1000efb8`…`0x1000f1e8` each end in `b 0x1000f26c` (verified encodings: `0xEA000044` at
  `0x1000f154`, `0xEA000021` at `0x1000f1e0`); `0x1000f2b0` is `BL 0x100093d0`
  (`0xEBFFE846`).
- `0x100093d0` writes `[r1+0x18]` = DEF (`rsb r3,r4,r3` → subtract).
- `r5`/`r8` roles cross-checked against `0x10005e98(game, r8, r5)`, which drains HP from `r5`
  and heals `r8`.

## Open questions

- Is the self-debuff intentional (cursed gear) or a swapped-argument bug? No item text in
  `itemdata.dat` describes these effects, so the data cannot settle it.
- Do the messages actually read "AGI Down" etc.? Message ids 10–16 are in `battlemes.dat`, which
  is Spanish in this dump and not yet indexed.
- Does the game cap a stat at 0? The setters do not clamp; a negative ATK would then flow into
  the damage formula, which is untested.
