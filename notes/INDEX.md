# Pocket Kingdom notes index

Start at [AGENT_CONTEXT.md](../AGENT_CONTEXT.md). Each note is self-contained and ends with
open questions. Status: ✅ verified at instruction level · 🟡 inferred / partial.

## Effects
- ✅ [Stat Up/Down (0–11)](effects/stat-modifiers.md) — Up = +25 % at battle start; Down = the
  **wearer's own** stat −INT(target)/4, and 5/7/9/11 all write DEF. `0x1000f484` / `0x1000f26c`
- ✅ [Status ailments (12/13/15/16/18/19/21/22)](effects/status-ailments.md) — sleep/paralysis/
  poison/silence; "deep/severe/strong" variants skip the accuracy check; per-action cure by
  WIS/2 or INT/2. `0x10007a3c`–`0x10007f48` / `0x1000a5f8`
- ✅ [Resistances (14/17/20/23)](effects/resistances.md) — battle-start immunity bits in
  `unit+0xc` `0x1000`/`0x2000`/`0x4000`/`0x8000`; no attack-time effect. `0x1000f934`–`0x1000f964`
- ✅ [Auto HP Restore 1/2/3 (24–26)](effects/auto-hp-restore.md) — 33-tick timer, heals 2/5/10 HP.
  `0x1000f974` / `0x10022384`
- ✅ [Gold Recovery Up 1/2/3 (49–51)](effects/gold-recovery.md) — battle gold ×1.2/1.5/2.0,
  highest tier only. `0x1000d900`
- ✅ [Critical 1/2/3 (29–31)](effects/critical.md) — 10/20/30 %, but the flag is written to the
  **victim**; equipped Critical does not boost the wielder's hit. `0x1000f370` / `0x1000e6a8`
- ✅ [HP Absorption 1/2 (27–28)](effects/hp-absorption.md) — drain `ATK-DEF` (min 3), heal ⅓ / ⅔.
  `0x10005e98` / `0x10005fdc`
- ✅ [Counter 1/2/3 (32–34)](effects/counter.md) — 20/40/60 %, 40 px front / 8 px back.
  `0x10022a70`
- ✅ [Physical / Magic reduction (35–39)](effects/damage-reduction.md) — ×0.8/0.6/0.5, magic ×0.75;
  39 is a duplicate of 38. `0x1000e7e4` / `0x1000e77c`

## Systems
- ✅ [Effect dispatch (two tables)](systems/effect-dispatch.md) — battle-start vs attack-time,
  who is `r5` vs `r8`. `0x1000f3a0` / `0x1000eda8`
- ✅ [Battle records & stat layout](systems/battle-records.md) — 92-byte stats, unit struct,
  effect-flag word, equipment slots

## Conventions
- Every note starts with a `> **TL;DR**` block so an agent can stop reading after 6 lines.
- `addresses:` in the frontmatter is the machine-readable list; the prose has the caller chain.
- Anything unproven goes under **Open questions**, never into the TL;DR.
