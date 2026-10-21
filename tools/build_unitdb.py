#!/usr/bin/env python3
"""Build a Pocket Kingdom unit database from the archived warcry.com unit pages.

Source (Wayback Machine capture, 2005-02-10):
  http://pk.warcry.com/units/                -> 115 units (index table)
  http://pk.warcry.com/units/view_unit.phtml?id=N
       -> per-unit Ability and an "Advances To" evolution table
          (target class, race, rank, level, VP, RankUp Emblem)
  http://pk.warcry.com/items/materials.phtml (2006-09-01)
       -> material database (jewels/ores/other): id, rarity, effect
  http://pk.warcry.com/items/view_material.phtml?id=N (2006-09-08)
       -> per-material Purchase In, Dropped By, Area Searches, Dungeon Reward

Outputs (default: ./unitdb/):
  units.json                 structured records (incl. ability + advances)
  units.csv                  spreadsheet-friendly
  emblems.json / .csv        emblem recipes (ore + 2 items + success)
  materials.json / .csv      material database (id, name, category, rarity, effect,
                             purchase locations, drops, area searches, dungeons)
  crafting.json / .csv       weapon/armor/accessory recipes (mold + ore + 2 items + effect + success)
  effects.json / .csv        effect id -> name table
  PocketKingdom-Units.html   self-contained app: units, team builder, emblems, materials, crafting
  raw/                       cached source pages (safe to delete)

The HTML app inlines the data so it works offline by double-clicking it
(no server, so no fetch/CORS issues).

Usage:
  python3 tools/build_unitdb.py                  # index only, fast
  python3 tools/build_unitdb.py --details        # + fetch each unit's page
  python3 tools/build_unitdb.py --details --emblems --crafting --materials --material-details
  python3 tools/build_unitdb.py --html saved.html
"""
from __future__ import annotations

import argparse
import csv
import html as htmlmod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TS = "20050210003854"
BASE = "http://pk.warcry.com"
DEFAULT_URL = f"https://web.archive.org/web/{TS}/{BASE}/units/"
EMBLEM_URL = f"https://web.archive.org/web/20050207131118/{BASE}/items/emblems.phtml"
MATERIAL_URL = f"https://web.archive.org/web/20060901040635/{BASE}/items/materials.phtml"
MATERIAL_DETAIL_URL = f"https://web.archive.org/web/20060908142300/{BASE}/items/view_material.phtml?id={{id}}"

STATS = ["hp", "atk", "def", "agi", "dex", "wis", "int", "hit"]
FIELDS = ["id", "name", "race", "race_icon", "rank", "slots", "move", "sp", *STATS,
          "ability", "advances"]
EMBLEM_FIELDS = ["emblem", "ore", "item1", "item2", "success"]
MATERIAL_FIELDS = ["id", "name", "category", "rarity", "effect",
                   "purchase_in", "dropped_by", "area_searches", "dungeon_reward"]
MATERIAL_DETAIL_SECTIONS = ("Purchase In", "Dropped By", "Area Searches", "Dungeon Reward")
CRAFT_FIELDS = ["mold", "ore", "item1", "item2", "result", "effect", "success", "effect_ids"]

# Effect behaviour that is *not* in the data files. effect.dat / the effect
# block of itemdata.dat only store the 52 names; the mechanics live in code.
# Verified in 6RAH.APP: IDs 40-43 are the last cases of the 44-entry dispatcher
# at 0x1000f3c8, and multiply the equipped unit's battle stats
# (ATK +0x14, DEF +0x18, AGI +0x24, DEX +0x28, WIS +0x2c, INT +0x30).
# See CLAUDE.md > "Item effects 40-43 (verified)".
EFFECT_BEHAVIOR = {
    27: "Attack proc: drain ATK-DEF (min 3) from the target, wielder heals 1/3 of it",
    28: "Attack proc: drain ATK-DEF (min 3) from the target, wielder heals 2/3 of it",
    29: "10% chance on hit: marks the target with the x2 damage flag (not the wielder)",
    30: "20% chance on hit: marks the target with the x2 damage flag (not the wielder)",
    31: "30% chance on hit: marks the target with the x2 damage flag (not the wielder)",
    32: "20% chance to counter a melee hit (attacker within 40px front / 8px back)",
    33: "40% chance to counter a melee hit (attacker within 40px front / 8px back)",
    34: "60% chance to counter a melee hit (attacker within 40px front / 8px back)",
    35: "Physical damage taken x0.8 (-20%); highest tier only",
    36: "Physical damage taken x0.6 (-40%); highest tier only",
    37: "Physical damage taken x0.5 (-50%); highest tier only",
    38: "Magic damage taken x0.75 (-25%)",
    39: "Magic damage taken x0.75 (-25%); same handler as 38 (no separate reflect code)",
    40: "INT +50% (x1.5)",
    41: "ATK & DEF +30% (x1.3)",
    42: "INT & WIS +30% (x1.3)",
    43: "ATK/DEF/AGI/DEX/WIS/INT +30% (x1.3)",
    44: "On death: 59px blast, damage = HP - target DEF (min 1)",
    45: "10% per action: heal 50% max HP",
    46: "10% per action: clone into an empty slot 4/5",
    47: "On death: revive once at 50% max HP (consumed)",
    48: "Battle end: a surviving carrier gives each fallen ally a 50% chance to keep its equipped item (kept unequipped; otherwise destroyed)",
}
GIST_URL = (
    "https://gist.githubusercontent.com/Apihplays/"
    "636c34a342b070188780f7f0a417d290/raw/"
    "df59bddaea4d7cb14c41ac89f5ef335d689c44ef/"
    "pocket%20kingdown%20own%20the%20world"
)
RANKUP_FIELDS = ["from", "to", "sp", "rank", "level", "vp", "emblem"]


# --------------------------------------------------------------------------- io
def fetch(url: str, tries: int = 3) -> str:
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pk-unitdb/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # noqa: PERF203
            last = e
            time.sleep(1.5 * (n + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def fetch_detail(uid: int, cache: Path) -> str:
    cached = cache / f"unit_{uid:03d}.html"
    if cached.exists() and cached.stat().st_size > 1000:
        return cached.read_text(encoding="utf-8", errors="replace")
    url = f"https://web.archive.org/web/{TS}/{BASE}/units/view_unit.phtml?id={uid}"
    page = fetch(url)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(page, encoding="utf-8")
    return page


# ------------------------------------------------------------------------ parse
def _text(cell: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", cell)).strip()


def _int(s: str) -> int:
    m = re.search(r"-?\d+", s)
    return int(m.group()) if m else 0


def parse_units(page: str) -> list[dict]:
    rows = [r for r in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page)
            if "view_unit.phtml?id=" in r]
    units: list[dict] = []
    for row in rows:
        cells = re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)
        if len(cells) < 14:
            continue
        ids = re.search(r"view_unit\.phtml\?id=(\d+)", row)
        if not ids:
            continue
        icon = re.search(r"race_icons/(\d+)\.gif", row)
        alts = re.findall(r'alt="([^"]*)"', cells[4] + cells[5])
        slot_alt = next((a for a in alts if "Slot" in a), "")
        move = next((a for a in alts if a in ("Walk", "Fly")), "")
        units.append({
            "id": int(ids.group(1)),
            "name": _text(cells[1]),
            "race": _text(cells[2]),
            "race_icon": int(icon.group(1)) if icon else 0,
            "rank": _int(_text(cells[3])),
            "slots": _int(slot_alt) or 1,
            "move": move or "Walk",
            "sp": None,
            **dict(zip(STATS, [_int(_text(cells[6 + i])) for i in range(8)])),
            "ability": "",
            "advances": [],
        })
    units.sort(key=lambda u: u["id"])
    return units


def parse_detail(page: str) -> dict:
    """Extract {ability, advances[]} from a per-unit page."""
    ability = ""
    m = re.search(r"Ability:\s*(.*?)\s*Hit Rate:", page, re.S)
    if m:
        ability = _text(m.group(1))

    advances: list[dict] = []
    m = re.search(r"Advances To\s*</div>(.*?)</table>", page, re.S)
    if m:
        for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", m.group(1)):
            if "view_unit.phtml?id=" not in row:
                continue
            cells = re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)
            if len(cells) < 7:
                continue
            tid = re.search(r"view_unit\.phtml\?id=(\d+)", cells[0])
            if not tid:
                continue
            advances.append({
                "id": int(tid.group(1)),
                "name": _text(cells[1]),
                "race": _text(cells[2]),
                "rank": _int(_text(cells[3])),
                "level": _int(_text(cells[4])),
                "vp": _int(_text(cells[5])),
                "emblem": _text(cells[6]),
            })
    return {"ability": ability, "advances": advances}


def parse_emblems(page: str) -> list[dict]:
    """Emblem Database rows: [#] Emblem | Ore | Item1 | Item2 | Success%."""
    rows = [r for r in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page)
            if "view_item.phtml?id=" in r]
    out: list[dict] = []
    for r in rows:
        cells = [_text(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", r)]
        if len(cells) < 6 or not cells[1]:
            continue
        out.append({
            "emblem": cells[1],
            "ore": cells[2],
            "item1": cells[3],
            "item2": cells[4],
            "success": _int(cells[5]),
        })
    return out


def parse_materials(page: str) -> list[dict]:
    """Material Database: category headers then Item | Rarity | Effect rows.

    Sections are ``Jewels``, ``Ores`` and ``Other Materials``; each row links
    to ``view_material.phtml?id=N``, which is the in-game material id.
    """
    out: list[dict] = []
    category = ""
    for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page):
        if 'class="TableHead"' in row and "view_material.phtml" not in row:
            head = re.search(r"<b>(.*?)</b>", row, re.S)
            if head:
                category = _text(head.group(1))
            continue
        ids = re.search(r"view_material\.phtml\?id=(\d+)", row)
        if not ids or not category:
            continue
        cells = [_text(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
        if len(cells) < 3 or not cells[0]:
            continue
        out.append({
            "id": int(ids.group(1)),
            "name": cells[0],
            "category": category,
            "rarity": _int(cells[1]),
            "effect": cells[2],
        })
    return out


def fetch_material_detail(mid: int, cache: Path) -> str:
    cached = cache / f"material_{mid:03d}.html"
    if cached.exists() and cached.stat().st_size > 1000:
        return cached.read_text(encoding="utf-8", errors="replace")
    page = fetch(MATERIAL_DETAIL_URL.format(id=mid))
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(page, encoding="utf-8")
    return page


def parse_material_detail(page: str) -> dict:
    """Where a material comes from, from its ``view_material.phtml`` page.

    The page is a stack of bold-titled tables; only four matter here:
      Purchase In     -> shop locations (one per row)
      Dropped By      -> units that drop it (# icon link, then name)
      Area Searches   -> area + ``Offline``/``Online`` search availability
      Dungeon Reward  -> dungeon, area, floor count
    Materials legitimately omit any of them, so every field defaults to [].
    """
    heads = list(re.finditer(
        r'font-size: 12pt; font-weight: bold; color: #000000;">(.*?)</div>', page, re.S))
    chunks: dict[str, str] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(page)
        chunks[_text(m.group(1))] = page[m.end():end]

    def rows(title: str) -> list[tuple[str, list[str]]]:
        out: list[tuple[str, list[str]]] = []
        for row in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", chunks.get(title, "")):
            if 'class="TableHead"' in row:
                continue
            cells = [_text(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
            if any(cells):
                out.append((row, cells))
        return out

    purchase_in: list[str] = []
    for _, cells in rows("Purchase In"):
        name = cells[0].strip()
        if name and name not in purchase_in:
            purchase_in.append(name)

    dropped_by: list[dict] = []
    for row, cells in rows("Dropped By"):
        uid = re.search(r"view_unit\.phtml\?id=(\d+)", row)
        if not uid or len(cells) < 2 or not cells[1]:
            continue
        dropped_by.append({"id": int(uid.group(1)), "name": cells[1]})

    area_searches: list[dict] = []
    for _, cells in rows("Area Searches"):
        if len(cells) < 2 or not cells[0]:
            continue
        area_searches.append({"area": cells[0], "status": cells[1]})

    dungeon_reward: list[dict] = []
    for _, cells in rows("Dungeon Reward"):
        if len(cells) < 3 or not cells[0]:
            continue
        dungeon_reward.append({"dungeon": cells[0], "area": cells[1],
                               "floors": _int(cells[2])})

    return {"purchase_in": purchase_in, "dropped_by": dropped_by,
            "area_searches": area_searches, "dungeon_reward": dungeon_reward}


def parse_crafting(text: str) -> tuple[list[dict], list[dict]]:
    """Parse the crafting chart + effect-id list out of the plain-text guide.

    Section layout (pipe-delimited):
        Mold | Ore | Item1 | Item2 | Result | Effect | Success
    followed later by an ``effect list`` of ``<id> <name>`` lines.
    """
    try:
        start = text.index("Weapons/Armors/Accessories Creation Chart")
    except ValueError:
        return [], []

    recipes: list[dict] = []
    for ln in text[start:].splitlines():
        if ln.startswith("====") and recipes:
            break
        if ln.count("|") != 6 or ln.lstrip().startswith("-"):
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) != 7 or not parts[6].endswith("%"):
            continue
        recipes.append({
            "mold": parts[0],
            "ore": parts[1],
            "item1": parts[2],
            "item2": parts[3],
            "result": parts[4],
            "effect": parts[5],
            "success": _int(parts[6]),
        })

    effects: list[dict] = []
    if "effect list" in text:
        for ln in text[text.index("effect list"):].splitlines()[1:]:
            m = re.match(r"^(\d+)\s+(.+?)\s*$", ln)
            if m:
                effects.append({"id": int(m.group(1)), "name": m.group(2)})

    for e in effects:
        e["behavior"] = EFFECT_BEHAVIOR.get(e["id"], "")

    for r in recipes:
        r["effect_ids"] = effect_ids_for(r["effect"], effects)
    return recipes, effects


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# Guide labels -> effect-list names. The chart uses internal spellings
# ("HPAbsortiopn1") and short forms ("DeadlyPoison"), so normalise explicitly.
_EFFECT_ALIASES = {
    "hpabsorption1": "hp absorp 1",
    "hpabsorption2": "hp absorp 2",
    "hpabsortiopn1": "hp absorp 1",
    "hpabsortiopn2": "hp absorp 2",
    "critical1": "critical 1",
    "critical2": "critical 2",
    "critical3": "critical 3",
    "counter1": "counter 1",
    "counter2": "counter 2",
    "counter3": "counter 3",
    "strongsilence": "severe silence",
    "deadlypoison": "severe poison",
    "physicalreduction1": "phy reduc 1",
    "physicalreduction2": "phy reduc 2",
    "physicalreduction3": "phy reduc 3",
    "goldrecoveryup1": "loot recovery up 1",
    "goldrecoveryup2": "loot recovery up 2",
    "goldrecoveryup3": "loot recovery up 3",
    "warriorsspirit": "warrior spirit",
    "magesspirit": "mage spirit",
    "herosspirit": "hero spirit",
}


# Ingredient names in the guide are matched against the warcry material names
# after normalisation (_norm here, M_NORM in the app). The chart has spelling
# slips; map them to the real material. ``Any`` is the guide's wildcard slot and
# intentionally matches nothing.
INGREDIENT_ALIASES = {
    "chaostheart": "chaosheart",   # "ChaostHeart" -> "Chaos Heart"
}
WILDCARD_INGREDIENTS = {"any"}


def effect_ids_for(label: str, effects: list[dict]) -> list[int]:
    """Map a chart effect label (possibly compound) to effect-list ids."""
    by_name = {_norm(e["name"]): e["id"] for e in effects}

    def lookup(part: str) -> int | None:
        key = _norm(part)
        key = _norm(_EFFECT_ALIASES.get(key, key))
        return by_name.get(key)

    whole = lookup(label)
    if whole is not None:
        return [whole]

    # Compound labels are space-separated, e.g. "HPAbsortiopn1 AutoHPRestore1".
    out: list[int] = []
    for part in label.split():
        val = lookup(part)
        if val is not None and val not in out:
            out.append(val)
    return out


def parse_rankup(text: str) -> list[dict]:
    """Parse the guide's unit rankup chart into evolution edges.

    Columns are ``Start | End | SP | Rank | Level | VP | Emblem`` but the guide
    is hand-written: some rows drop the SP cell entirely, and some merge SP and
    Rank into one cell (``"14    5"``). ``->`` continues the previous start unit.
    SP belongs to the *source unit*, so it is propagated to all its rows.
    """
    try:
        start = text.index("UNIT RANKUP CHART")
        end = text.index("EMBLEM CREATION CHART")
    except ValueError:
        return []
    section = text[start:end]

    def num(cell: str) -> int | None:
        m = re.search(r"\d+", cell)
        return int(m.group()) if m else None

    rows: list[dict] = []
    prev: str | None = None
    for ln in section.splitlines():
        if "|" not in ln or re.fullmatch(r"[-\s|]+", ln) or "Start Unit" in ln:
            continue
        parts = [c.strip() for c in ln.split("|")]
        if len(parts) == 7:
            sp, rank, level, vp, emblem = (num(parts[2]), num(parts[3]),
                                           num(parts[4]), num(parts[5]), parts[6])
        elif len(parts) == 6:
            merged = re.findall(r"\d+", parts[2])
            if len(merged) >= 2:  # SP and Rank squeezed into one cell
                sp, rank = int(merged[0]), int(merged[1])
            else:                 # SP cell missing entirely
                sp, rank = None, num(parts[2])
            level, vp, emblem = num(parts[3]), num(parts[4]), parts[5]
        else:
            continue
        src = prev if parts[0] == "->" else parts[0]
        prev = src
        rows.append({"from": src, "to": parts[1], "sp": sp,
                     "rank": rank, "level": level, "vp": vp, "emblem": emblem})

    # SP is recorded once, on the first row of each source-unit group.
    first_sp = {r["from"]: r["sp"] for r in rows if r["sp"] is not None}
    for r in rows:
        r["sp"] = first_sp.get(r["from"])
    return rows


def merge_sp(units: list[dict], rankup: list[dict]) -> int:
    """Attach the guide's SP value to each unit (blank when the guide omits it)."""
    sp_by_unit = {}
    for r in rankup:
        if r["sp"] is not None:
            sp_by_unit.setdefault(r["from"], r["sp"])
    n = 0
    for u in units:
        u["sp"] = sp_by_unit.get(u["name"])
        n += u["sp"] is not None
    return n


def crosscheck_rankup(units: list[dict], rankup: list[dict]) -> dict:
    """Compare scraped evolution edges against the guide's chart."""
    mine = {(u["name"], a["name"]): a for u in units for a in u["advances"]}
    guide = {(r["from"], r["to"]): r for r in rankup}
    shared = set(mine) & set(guide)
    fields = ("rank", "level", "vp", "emblem")
    diffs = [(k, f, guide[k][f], mine[k][f])
             for k in sorted(shared) for f in fields if guide[k][f] != mine[k][f]]
    return {
        "scraped": len(mine), "guide": len(guide), "shared": len(shared),
        "agree": len(shared) - len({k for k, *_ in diffs}),
        "diffs": diffs,
        "only_guide": sorted(set(guide) - set(mine)),
        "only_scraped": sorted(set(mine) - set(guide)),
    }


# ------------------------------------------------------------------------- html
HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pocket Kingdom - Compendium</title>
<style>
  :root{--bg:#12141a;--panel:#1b1e27;--panel2:#222634;--line:#333a4d;--txt:#e6e9f0;
        --dim:#98a0b3;--accent:#f0b429;--accent2:#4aa3ff;--good:#57d38c;--bad:#ff6b6b}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
       font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:14px 20px;border-bottom:1px solid var(--line);
         background:linear-gradient(180deg,#1e2230,#171a23);position:sticky;top:0;z-index:5}
  h1{margin:0;font-size:18px;letter-spacing:.3px}
  h1 span{color:var(--accent)}
  .sub{color:var(--dim);font-size:12px;margin-top:3px}
  .tabs{display:flex;gap:8px;margin-top:10px}
  .tab{background:transparent;border:1px solid var(--line);color:var(--dim);
       border-radius:8px;padding:6px 14px;cursor:pointer;font-size:13px}
  .tab.on{background:var(--panel2);color:var(--txt);border-color:var(--accent)}
  .wrap{padding:16px 20px 80px;max-width:1500px;margin:0 auto}
  .controls{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;
            background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
  .fld{display:flex;flex-direction:column;gap:5px}
  .fld label{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim)}
  input,select{background:var(--panel2);border:1px solid var(--line);color:var(--txt);
               border-radius:7px;padding:7px 9px;font-size:13px;min-width:70px}
  input[type=number]{width:80px}
  input[type=search]{min-width:200px}
  .chips{display:flex;gap:6px}
  .chip{border:1px solid var(--line);background:var(--panel2);color:var(--dim);
        border-radius:999px;padding:6px 13px;cursor:pointer;font-size:13px;user-select:none}
  .chip.on{background:var(--accent);border-color:var(--accent);color:#20180a;font-weight:600}
  .btn{background:var(--accent2);border:none;color:#04121f;font-weight:600;border-radius:7px;
       padding:8px 14px;cursor:pointer;font-size:13px}
  .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--dim);font-weight:500}
  .btn.mini{padding:3px 9px;font-size:12px;border-radius:6px}
  .meta{display:flex;justify-content:space-between;align-items:center;gap:10px;
        margin:16px 2px 8px;color:var(--dim);font-size:12.5px;flex-wrap:wrap}
  table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
  th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
  th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),
  th:nth-child(3),td:nth-child(3){text-align:left}
  thead th{position:sticky;top:0;background:#1a1d27;cursor:pointer;color:var(--dim);
           font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;z-index:2}
  thead th:hover{color:var(--txt)}
  thead th.sorted{color:var(--accent)}
  tbody tr:nth-child(odd){background:rgba(255,255,255,.015)}
  tbody tr:hover{background:rgba(74,163,255,.10);cursor:pointer}
  .name{font-weight:600}
  .race{color:var(--dim)}
  .best{color:var(--good);font-weight:700}
  .slot1{color:var(--good)}.slot2{color:var(--accent)}.slot3{color:#ff8f6b}
  .tagbar{display:flex;gap:6px;flex-wrap:wrap}
  .tag{font-size:11px;color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:2px 7px}
  .empty{padding:40px;text-align:center;color:var(--dim)}
  /* modal */
  .backdrop{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;z-index:20}
  .backdrop.on{display:block}
  .modal{position:fixed;z-index:21;top:50%;left:50%;transform:translate(-50%,-50%);
         width:min(680px,92vw);max-height:88vh;overflow:auto;background:var(--panel);
         border:1px solid var(--line);border-radius:12px;padding:20px;display:none}
  .modal.on{display:block}
  .modal h2{margin:0 0 2px}
  .modal .m-sub{color:var(--dim);font-size:12.5px;margin-bottom:14px}
  .statgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}
  .statgrid div{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
  .statgrid b{display:block;font-size:11px;color:var(--dim);letter-spacing:.5px}
  .statgrid span{font-size:16px;font-weight:600}
  .sect{margin-top:16px}
  .sect h3{font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim);margin:0 0 8px}
  .adv{display:flex;justify-content:space-between;gap:10px;padding:7px 10px;
       border:1px solid var(--line);border-radius:8px;margin-bottom:6px;
       background:var(--panel2);cursor:pointer}
  .adv:hover{border-color:var(--accent2)}
  .adv .r{color:var(--dim);font-size:12px;text-align:right}
  .abilitybox{background:rgba(240,180,41,.12);border:1px solid rgba(240,180,41,.4);
              color:var(--accent);border-radius:8px;padding:8px 11px;font-weight:600;display:inline-block}
  .close{position:absolute;top:12px;right:14px;background:none;border:none;color:var(--dim);
         font-size:22px;cursor:pointer;line-height:1}
  /* team */
  .teamgrid{display:grid;grid-template-columns:1.4fr .9fr;gap:18px;align-items:start}
  @media(max-width:900px){.teamgrid{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
  .card h3{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim)}
  .slotbar{height:12px;background:var(--panel2);border-radius:999px;overflow:hidden;border:1px solid var(--line)}
  .slotbar>i{display:block;height:100%;background:var(--good)}
  .slotbar.over>i{background:var(--bad)}
  .trow{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
  .trow .nm{flex:1}
  .trow .st{color:var(--dim);font-size:12px}
  #tab-emblems th,#tab-emblems td{text-align:left}
  #tab-emblems th:last-child,#tab-emblems td:last-child{text-align:right}
  #tab-crafting th,#tab-crafting td{text-align:left}
  #tab-crafting th:last-child,#tab-crafting td:last-child{text-align:right}
  #tab-crafting th:nth-child(7),#tab-crafting td:nth-child(7){text-align:right}
  #tab-materials th,#tab-materials td{text-align:left}
  #tab-materials th:nth-child(3),#tab-materials td:nth-child(3),
  #tab-materials th:nth-child(7),#tab-materials td:nth-child(7){text-align:right}
  details summary{cursor:pointer;color:var(--dim);font-size:12.5px;margin-top:18px}
  details summary:hover{color:var(--txt)}
  .eid{color:var(--dim);font-size:11px;font-weight:400}
  .rate30{color:var(--good);font-weight:700}
  .rate20{color:var(--accent)}
  .rate10{color:#ff8f6b}
  .rate5{color:var(--bad);font-weight:700}
  .emlink{cursor:pointer;border-bottom:1px dotted var(--dim)}
  .emlink:hover{color:var(--accent2);border-color:var(--accent2)}
  a{color:var(--accent2)}
  footer{color:#5c6478;font-size:11.5px;padding:0 20px 40px;max-width:1500px;margin:0 auto}
</style>
</head>
<body>
<header>
  <h1>Pocket Kingdom <span>Compendium</span></h1>
  <div class="sub">__COUNT__ units &middot; __MATCOUNT__ materials &middot; source: pk.warcry.com (Wayback Machine 2005-02-10) &middot; offline</div>
  <div class="tabs">
    <button class="tab on" data-tab="units">Units</button>
    <button class="tab" data-tab="team">Team Builder</button>
    <button class="tab" data-tab="emblems">Emblems</button>
    <button class="tab" data-tab="materials">Materials</button>
    <button class="tab" data-tab="crafting">Crafting</button>
  </div>
</header>

<div class="wrap">
  <!-- UNITS -->
  <section id="tab-units">
    <div class="controls">
      <div class="fld"><label>Search</label>
        <input id="q" type="search" placeholder="name, race or ability..."></div>
      <div class="fld"><label>Race</label><select id="race"><option value="">All</option></select></div>
      <div class="fld"><label>Move</label>
        <select id="move"><option value="">Any</option><option>Walk</option><option>Fly</option></select></div>
      <div class="fld"><label>Slots</label>
        <div class="chips" id="slots">
          <span class="chip on" data-v="0">Any</span><span class="chip" data-v="1">1</span>
          <span class="chip" data-v="2">2</span><span class="chip" data-v="3">3</span></div></div>
      <div class="fld"><label>Rank min-max</label>
        <div style="display:flex;gap:6px;align-items:center">
          <input id="rmin" type="number" min="1" max="9" placeholder="1">
          <span style="color:var(--dim)">-</span>
          <input id="rmax" type="number" min="1" max="9" placeholder="9"></div></div>
      <div class="fld"><label>Rank by</label><select id="sort"></select></div>
      <div class="fld"><label>&nbsp;</label><button class="btn ghost" id="reset">Reset</button></div>
    </div>
    <div class="meta"><div id="count"></div><div class="tagbar" id="tags"></div></div>
    <table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table>
    <div class="empty" id="empty" style="display:none">No units match these filters.</div>
  </section>

  <!-- TEAM -->
  <section id="tab-team" style="display:none">
    <div class="teamgrid">
      <div class="card">
        <h3>Your team</h3>
        <div id="team-list"></div>
        <div class="empty" id="team-empty">No units yet. Open the <b>Units</b> tab and click <b>+</b> on a row.</div>
        <div style="margin-top:12px;display:flex;gap:10px">
          <button class="btn ghost mini" id="team-clear">Clear team</button>
        </div>
      </div>
      <div class="card">
        <h3>Slots &amp; totals</h3>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <label style="color:var(--dim);font-size:12px">Slot cap</label>
          <input id="cap" type="number" min="1" value="30" style="width:90px">
          <span id="slot-txt" style="font-variant-numeric:tabular-nums"></span>
        </div>
        <div class="slotbar" id="slotbar"><i style="width:0%"></i></div>
        <div class="statgrid" id="totals"></div>
      </div>
    </div>
  </section>

  <!-- EMBLEMS -->
  <section id="tab-emblems" style="display:none">
    <div class="controls">
      <div class="fld"><label>Search</label>
        <input id="eq" type="search" placeholder="emblem, ore or item..."></div>
      <div class="fld"><label>&nbsp;</label><button class="btn ghost" id="eclear">Clear</button></div>
    </div>
    <div class="meta"><div id="ecount"></div><div class="tagbar" id="etags"></div></div>
    <table><thead><tr><th>Emblem</th><th>Ore</th><th>Item 1</th><th>Item 2</th><th>Success</th></tr></thead>
      <tbody id="ebody"></tbody></table>
    <div class="empty" id="eempty" style="display:none">No emblem recipes match.</div>
    <p style="color:var(--dim);font-size:12.5px;margin-top:12px">
      Each emblem also consumes one <b>RankUp mold</b> (bought in the Shop from
      map 2 onward) in addition to the three materials below.
    </p>
  </section>

  <!-- MATERIALS -->
  <section id="tab-materials" style="display:none">
    <div class="controls">
      <div class="fld"><label>Search</label>
        <input id="mq" type="search" placeholder="material, effect or location..."></div>
      <div class="fld"><label>Category</label>
        <div class="chips" id="mcat">
          <span class="chip on" data-v="">All</span>
          <span class="chip" data-v="Jewels">Jewels</span>
          <span class="chip" data-v="Ores">Ores</span>
          <span class="chip" data-v="Other Materials">Other</span></div></div>
      <div class="fld"><label>Rarity min-max</label>
        <div style="display:flex;gap:6px;align-items:center">
          <input id="mmin" type="number" min="1" max="10" placeholder="1">
          <span style="color:var(--dim)">-</span>
          <input id="mmax" type="number" min="1" max="10" placeholder="10"></div></div>
      <div class="fld"><label>Sold in</label>
        <select id="mshop"><option value="">Any shop</option></select></div>
      <div class="fld"><label>Rank by</label>
        <select id="msort">
          <option value="rarity">Rarity</option>
          <option value="name">Item</option>
          <option value="category">Category</option>
          <option value="effect">Effect</option>
          <option value="shops">Shops</option>
          <option value="uses">Recipes</option>
        </select></div>
      <div class="fld"><label>&nbsp;</label><button class="btn ghost" id="mclear">Clear</button></div>
    </div>
    <div class="meta"><div id="mcount"></div><div class="tagbar" id="mtags"></div></div>
    <table><thead><tr>
      <th>Item</th><th>Category</th><th>Rarity</th><th>Effect</th>
      <th>Where</th><th>Used in</th>
    </tr></thead><tbody id="mbody"></tbody></table>
    <div class="empty" id="mempty" style="display:none">No materials match.</div>
    <p style="color:var(--dim);font-size:12.5px;margin-top:12px">
      Click a material for shops that sell it, the areas you can search, dungeons
      that reward it, units that drop it, and the crafting/emblem recipes that
      consume it. Rarity is the warcry.com value (higher = rarer). Recipe counts
      only cover the crafting and emblem tables here, so a dash means no known
      recipe — not that the material is useless in game.
    </p>
  </section>

  <!-- CRAFTING -->
  <section id="tab-crafting" style="display:none">
    <div class="controls">
      <div class="fld"><label>Search</label>
        <input id="kq" type="search" placeholder="result, ore, material or effect..."></div>
      <div class="fld"><label>Mold</label>
        <select id="kmold"><option value="">All molds</option></select></div>
      <div class="fld"><label>Ore</label>
        <select id="kore"><option value="">Any ore</option></select></div>
      <div class="fld"><label>Success &le;</label>
        <select id="krate">
          <option value="">Any</option><option value="30">30% or less</option>
          <option value="20">20% or less</option><option value="10">10% or less</option>
        </select></div>
      <div class="fld"><label>Rank by</label>
        <select id="ksort">
          <option value="success">Success</option>
          <option value="mold">Mold</option>
          <option value="result">Result</option>
          <option value="ore">Ore</option>
        </select></div>
      <div class="fld"><label>&nbsp;</label><button class="btn ghost" id="kclear">Clear</button></div>
    </div>
    <div class="meta"><div id="kcount"></div><div class="tagbar" id="ktags"></div></div>
    <table><thead><tr>
      <th>Mold</th><th>Ore</th><th>Material 1</th><th>Material 2</th>
      <th>Result</th><th>Effect</th><th>Success</th>
    </tr></thead><tbody id="kbody"></tbody></table>
    <div class="empty" id="kempty" style="display:none">No crafting recipes match.</div>

    <details>
      <summary>Effect id reference (__EFFECTCOUNT__ effects)</summary>
      <table style="margin-top:8px"><thead><tr><th>ID</th><th>Effect</th><th>Behaviour</th></tr></thead>
        <tbody id="fbody"></tbody></table>
      <p class="sub">IDs 40&ndash;48 were verified in the game binary: 40&ndash;43 multiply
      the equipped unit&rsquo;s battle stats, 44&ndash;47 are death / per-action procs, and
      48 is the post-battle item-recovery roll. The other effects only have a name in
      the data files.</p>
    </details>
  </section>
</div>

<div class="backdrop" id="backdrop"></div>
<div class="modal" id="modal"><button class="close" id="modal-close">&times;</button><div id="modal-body"></div></div>

<footer>
  Base values from the 2005 warcry.com capture; the retail game scales HP/stats with level
  (and combine/evolution changes them). Slot cap is your own planning number.
  Not affiliated with Nokia or the game's rights holders.
</footer>

<script>
const UNITS = __DATA__;
const EMBLEMS = __EMBLEMS__;
const MATERIALS = __MATERIALS__;
const CRAFTING = __CRAFTING__;
const EFFECTS = __EFFECTS__;
const BY_ID = Object.fromEntries(UNITS.map(u=>[u.id,u]));
const MAT_BY_ID = Object.fromEntries(MATERIALS.map(m=>[m.id,m]));
const STATS = ["hp","atk","def","agi","dex","wis","int","hit"];
const LABEL = {hp:"HP",atk:"ATK",def:"DEF",agi:"AGI",dex:"DEX",wis:"WIS",int:"INT",hit:"HIT%"};
const COLS = [["name","Class"],["race","Race"],["rank","Rank"],["slots","Slots"],["move","Move"],
              ...STATS.map(s=>[s,LABEL[s]])];
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let sortKey="agi", sortDir=-1;
let team = [];                       // array of unit ids (duplicates allowed)
try { team = JSON.parse(localStorage.getItem("pk_team") || "[]"); } catch(e){ team = []; }
const saveTeam = () => localStorage.setItem("pk_team", JSON.stringify(team));

// ---- tabs
function showTab(name){
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("on", x.dataset.tab === name));
  ["units","team","emblems","materials","crafting"]
    .forEach(n => $("tab-"+n).style.display = n === name ? "" : "none");
}
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  showTab(t.dataset.tab);
  if (t.dataset.tab === "team") renderTeam();
  if (t.dataset.tab === "emblems") renderEmblems();
  if (t.dataset.tab === "materials") renderMaterials();
  if (t.dataset.tab === "crafting") renderCrafting();
});

// ---- controls
[...new Set(UNITS.map(u=>u.race))].sort().forEach(r=>{
  const o=document.createElement("option"); o.textContent=r; $("race").appendChild(o); });
COLS.forEach(([k,l])=>{ const o=document.createElement("option"); o.value=k; o.textContent=l; $("sort").appendChild(o); });
$("sort").value="agi"; $("sort").onchange=()=>{ sortKey=$("sort").value; sortDir=(sortKey==="name"||sortKey==="race"||sortKey==="move")?1:-1; renderUnits(); };
$("head").innerHTML = COLS.map(([k,l])=>`<th data-k="${k}">${l}</th>`).join("") + "<th></th>";
$("head").querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{ const k=th.dataset.k;
  if(sortKey===k) sortDir=-sortDir; else { sortKey=k; sortDir=(k==="name"||k==="race"||k==="move")?1:-1; }
  $("sort").value=k; renderUnits(); });
$("slots").querySelectorAll(".chip").forEach(c=>c.onclick=()=>{
  $("slots").querySelectorAll(".chip").forEach(x=>x.classList.remove("on")); c.classList.add("on"); renderUnits(); });
["q","race","move","rmin","rmax"].forEach(id=>$(id).addEventListener("input",renderUnits));
$("reset").onclick=()=>{ ["q","race","move","rmin","rmax"].forEach(id=>$(id).value="");
  $("sort").value="agi"; sortKey="agi"; sortDir=-1;
  $("slots").querySelectorAll(".chip").forEach((x,i)=>x.classList.toggle("on", i===0)); renderUnits(); };

const activeSlots = () => +$("slots").querySelector(".chip.on").dataset.v;

function filtered(){
  const q=$("q").value.trim().toLowerCase(), race=$("race").value, move=$("move").value,
        sl=activeSlots(), rmin=+$("rmin").value||0, rmax=+$("rmax").value||99;
  return UNITS.filter(u=>{
    if(q && !(u.name.toLowerCase().includes(q) || u.race.toLowerCase().includes(q)
              || (u.ability||"").toLowerCase().includes(q))) return false;
    if(race && u.race!==race) return false;
    if(move && u.move!==move) return false;
    if(sl && u.slots!==sl) return false;
    if(u.rank<rmin || u.rank>rmax) return false;
    return true;
  });
}

function renderUnits(){
  const rows = filtered().sort((a,b)=>{
    const x=a[sortKey], y=b[sortKey];
    return typeof x==="string" ? sortDir*x.localeCompare(y) : sortDir*(x-y);
  });
  $("head").querySelectorAll("th[data-k]").forEach(th=>th.classList.toggle("sorted", th.dataset.k===sortKey));
  $("count").textContent = `${rows.length} of ${UNITS.length} units`;
  $("empty").style.display = rows.length ? "none" : "block";

  const best={}; STATS.forEach(s=>{ best[s] = rows.length ? Math.max(...rows.map(r=>r[s])) : null; });
  const tags=[]; if(activeSlots()) tags.push(`${activeSlots()}-slot only`);
  if($("move").value) tags.push($("move").value); if($("race").value) tags.push($("race").value);
  if(!tags.length) tags.push("all units");
  $("tags").innerHTML = tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")
    + (rows.length ? `<span class="tag">best ${LABEL[sortKey]||sortKey}: <b style="color:var(--good)">${best[sortKey]??""}</b></span>` : "");

  $("body").innerHTML = rows.map(u=>{
    const cells = COLS.map(([k])=>{
      if(k==="name")  return `<td><span class="name">${esc(u.name)}</span>${u.ability?' <span title="Ability" style="color:var(--accent)">&#9733;</span>':''}</td>`;
      if(k==="race")  return `<td><span class="race">${esc(u.race)}</span></td>`;
      if(k==="slots") return `<td class="slot${u.slots}">${u.slots}</td>`;
      if(STATS.includes(k)) return `<td${best[k]===u[k]&&rows.length>1?' class="best"':''}>${u[k]}</td>`;
      return `<td>${esc(u[k])}</td>`;
    }).join("");
    return `<tr data-id="${u.id}">${cells}<td><button class="btn mini" data-add="${u.id}" title="Add to team">+</button></td></tr>`;
  }).join("");

  $("body").querySelectorAll("tr[data-id]").forEach(tr=>tr.onclick=e=>{
    if(e.target.closest("button")) return; openDetail(+tr.dataset.id); });
  $("body").querySelectorAll("button[data-add]").forEach(b=>b.onclick=e=>{
    e.stopPropagation(); team.push(+b.dataset.add); saveTeam(); flash(b); renderTeam(); });
}

function flash(b){ const t=b.textContent; b.textContent="ok"; setTimeout(()=>b.textContent=t, 600); }

// ---- detail modal
function openDetail(id){
  const u=BY_ID[id]; if(!u) return;
  const stats = STATS.map(s=>`<div><b>${LABEL[s]}</b><span>${u[s]}</span></div>`).join("");
  const adv = (u.advances||[]).map(a=>`
      <div class="adv" data-go="${a.id}">
        <div><b>${esc(a.name)}</b> <span class="race" style="color:var(--dim)">${esc(a.race)}</span></div>
        <div class="r">Rank ${a.rank} &middot; Lvl ${a.level} &middot; ${a.vp} VP<br><span class="emlink" data-emblem="${esc(a.emblem||"")}">${esc(a.emblem||"-")}</span></div>
      </div>`).join("") || `<div class="empty" style="padding:14px">No evolution (final / unique unit).</div>`;
  $("modal-body").innerHTML = `
    <h2>${esc(u.name)}</h2>
    <div class="m-sub">${esc(u.race)} &middot; Rank ${u.rank} &middot; ${u.slots} slot${u.slots>1?"s":""} &middot; ${u.move}${u.sp!=null&&u.sp!==undefined?` &middot; SP ${u.sp}`:""}</div>
    ${u.ability?`<div class="abilitybox">${esc(u.ability)}</div>`:`<div style="color:var(--dim)">No special ability</div>`}
    <div class="statgrid">${stats}</div>
    <div class="sect"><h3>Advances to</h3>${adv}</div>
    <div class="sect"><button class="btn" id="m-add">Add to team</button></div>`;
  $("modal").classList.add("on"); $("backdrop").classList.add("on");
  $("m-add").onclick=()=>{ team.push(u.id); saveTeam(); renderTeam(); $("m-add").textContent="Added ✓"; };
  $("modal-body").querySelectorAll(".adv[data-go]").forEach(d=>d.onclick=()=>openDetail(+d.dataset.go));
  $("modal-body").querySelectorAll(".emlink[data-emblem]").forEach(s=>s.onclick=e=>{
    e.stopPropagation(); if(s.dataset.emblem) showEmblem(s.dataset.emblem); });
}
function closeModal(){ $("modal").classList.remove("on"); $("backdrop").classList.remove("on"); }
$("modal-close").onclick=closeModal; $("backdrop").onclick=closeModal;
document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeModal(); });

// ---- team builder
$("cap").value = +(localStorage.getItem("pk_cap") || 30);
$("cap").oninput = () => { localStorage.setItem("pk_cap", $("cap").value); renderTeam(); };
$("team-clear").onclick = () => { team=[]; saveTeam(); renderTeam(); };

function teamCounts(){ const m=new Map(); team.forEach(id=>m.set(id,(m.get(id)||0)+1)); return m; }

function renderTeam(){
  const counts = teamCounts();
  const ids = [...counts.keys()];
  $("team-empty").style.display = ids.length ? "none" : "block";
  $("team-list").innerHTML = ids.map(id=>{
    const u=BY_ID[id], n=counts.get(id);
    return `<div class="trow">
      <span class="nm">${n>1?`<b>${n}&times;</b> `:""}${esc(u.name)}
        <span class="race">${esc(u.race)}</span></span>
      <span class="st">${u.slots*n} slot${u.slots*n>1?"s":""}</span>
      <button class="btn mini ghost" data-dec="${id}">&minus;</button>
      <button class="btn mini" data-inc="${id}">+</button>
    </div>`;
  }).join("");
  $("team-list").querySelectorAll("button[data-inc]").forEach(b=>b.onclick=()=>{ team.push(+b.dataset.inc); saveTeam(); renderTeam(); });
  $("team-list").querySelectorAll("button[data-dec]").forEach(b=>b.onclick=()=>{ const id=+b.dataset.dec;
    const i=team.lastIndexOf(id); if(i>=0) team.splice(i,1); saveTeam(); renderTeam(); });

  const used = team.reduce((s,id)=>s+BY_ID[id].slots, 0);
  const cap = +$("cap").value || 0;
  $("slot-txt").innerHTML = `<b style="color:${cap&&used>cap?'var(--bad)':'var(--good)'}">${used}</b> / ${cap||"-"} slots`;
  const bar=$("slotbar"); bar.classList.toggle("over", !!(cap&&used>cap));
  bar.firstElementChild.style.width = Math.min(100, cap? used/cap*100 : 0) + "%";

  $("totals").innerHTML = STATS.map(s=>{
    const v = team.reduce((a,id)=>a+BY_ID[id][s], 0);
    return `<div><b>${LABEL[s]}</b><span>${v}</span></div>`; }).join("");
}

// ---- emblems
function renderEmblems(){
  const q = $("eq").value.trim().toLowerCase();
  const rows = EMBLEMS.filter(e =>
    !q || (e.emblem+" "+e.ore+" "+e.item1+" "+e.item2).toLowerCase().includes(q));
  $("ecount").textContent = `${rows.length} of ${EMBLEMS.length} recipes`;
  $("eempty").style.display = rows.length ? "none" : "block";
  const nem = new Set(rows.map(r=>r.emblem)).size;
  const rates = [...new Set(rows.map(r=>r.success))].sort((a,b)=>a-b);
  $("etags").innerHTML = `<span class="tag">${nem} emblems</span>`
    + rates.map(s=>`<span class="tag">${s}% success</span>`).join("");
  $("ebody").innerHTML = rows.map(e=>`<tr>
      <td><b>${esc(e.emblem)}</b></td><td>${esc(e.ore)}</td>
      <td>${esc(e.item1)}</td><td>${esc(e.item2)}</td>
      <td style="color:var(--good)">${e.success}%</td></tr>`).join("");
}
$("eq").addEventListener("input", renderEmblems);
$("eclear").onclick = () => { $("eq").value = ""; renderEmblems(); };
function showEmblem(name){
  closeModal(); showTab("emblems");
  $("eq").value = String(name).replace(/\s*Emblem$/i, "");
  renderEmblems();
  window.scrollTo({top:0, behavior:"smooth"});
}

// ---- materials
const M_NORM = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
// Guide spelling slips -> the real material name (mirrors INGREDIENT_ALIASES).
const ING_ALIAS = __INGALIAS__;
const M_KEY = s => ING_ALIAS[M_NORM(s)] || M_NORM(s);
function materialUses(m){
  const key = M_KEY(m.name);
  const hit = x => M_KEY(x) === key;
  return {
    craft: CRAFTING.filter(c => [c.ore, c.item1, c.item2].some(hit)),
    emblems: EMBLEMS.filter(e => [e.ore, e.item1, e.item2].some(hit)),
  };
}

const matShops = m => m.purchase_in || [];
const matAreas = m => m.area_searches || [];
const matDungeons = m => m.dungeon_reward || [];
const matDrops = m => m.dropped_by || [];
function whereParts(m){
  const p = matShops(m).length, a = new Set(matAreas(m).map(x=>x.area)).size,
        d = matDungeons(m).length, k = matDrops(m).length;
  const out = [];
  if (p) out.push(`${p} shop${p>1?"s":""}`);
  if (a) out.push(`${a} area${a>1?"s":""}`);
  if (d) out.push(`${d} dungeon${d>1?"s":""}`);
  if (k) out.push(`${k} drop${k>1?"s":""}`);
  return out;
}
function whereTitle(m){
  const bits = [];
  if (matShops(m).length) bits.push("Buy: " + matShops(m).join(", "));
  const areas = matAreas(m).map(a=>`${a.area} (${a.status})`);
  if (areas.length) bits.push("Search: " + areas.join(", "));
  if (matDungeons(m).length) bits.push("Dungeons: " + matDungeons(m).map(d=>d.dungeon).join(", "));
  if (matDrops(m).length) bits.push("Drops: " + matDrops(m).map(d=>d.name).join(", "));
  return bits.join(" | ");
}

function renderMaterials(){
  const q = $("mq").value.trim().toLowerCase();
  const cat = $("mcat").querySelector(".chip.on").dataset.v;
  const lo = +$("mmin").value || 0, hi = +$("mmax").value || 99;
  const shop = $("mshop").value;
  const key = $("msort").value;
  const rows = MATERIALS.filter(m => {
    if (cat && m.category !== cat) return false;
    if (m.rarity < lo || m.rarity > hi) return false;
    if (shop && !matShops(m).includes(shop)) return false;
    if (q) {
      const hay = [m.name, m.category, m.effect, ...matShops(m),
                   ...matAreas(m).map(a=>a.area), ...matDungeons(m).map(d=>d.dungeon),
                   ...matDrops(m).map(d=>d.name)].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }).map(m => { const use = materialUses(m); return {m, ...use, uses: use.craft.length + use.emblems.length}; });

  rows.sort((a,b) => {
    if (key === "name")     return a.m.name.localeCompare(b.m.name);
    if (key === "category") return a.m.category.localeCompare(b.m.category) || b.m.rarity - a.m.rarity;
    if (key === "effect")   return a.m.effect.localeCompare(b.m.effect) || a.m.name.localeCompare(b.m.name);
    if (key === "shops")    return matShops(b.m).length - matShops(a.m).length || a.m.name.localeCompare(b.m.name);
    if (key === "uses")     return b.uses - a.uses || a.m.name.localeCompare(b.m.name);
    return b.m.rarity - a.m.rarity || a.m.name.localeCompare(b.m.name);
  });

  $("mcount").textContent = `${rows.length} of ${MATERIALS.length} materials`;
  $("mempty").style.display = rows.length ? "none" : "block";
  const tags = [cat || "all categories"];
  if (q) tags.push(`"${q}"`);
  if (shop) tags.push(shop);
  if (lo || hi < 99) tags.push(`rarity ${lo || 1}-${hi < 99 ? hi : 10}`);
  const rarest = rows.length ? Math.max(...rows.map(r => r.m.rarity)) : null;
  $("mtags").innerHTML = tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")
    + (rarest !== null ? `<span class="tag">max rarity: <b style="color:var(--good)">${rarest}</b></span>` : "");

  $("mbody").innerHTML = rows.map(({m, uses}) => {
    const parts = whereParts(m);
    return `<tr data-mat="${m.id}">
      <td><span class="name">${esc(m.name)}</span></td>
      <td><span class="race">${esc(m.category)}</span></td>
      <td>${m.rarity}</td>
      <td>${m.effect && m.effect !== "-" ? esc(m.effect) : '<span style="color:var(--dim)">-</span>'}</td>
      <td title="${esc(whereTitle(m))}">${parts.length ? parts.join(" &middot; ") : '<span style="color:var(--dim)">-</span>'}</td>
      <td>${uses ? uses : '<span style="color:var(--dim)">-</span>'}</td></tr>`;
  }).join("");
  $("mbody").querySelectorAll("tr[data-mat]").forEach(tr=>tr.onclick=()=>openMaterial(+tr.dataset.mat));
}

function openMaterial(id){
  const m = MAT_BY_ID[id]; if (!m) return;
  const {craft, emblems} = materialUses(m);
  const shops = matShops(m), areas = matAreas(m), dungeons = matDungeons(m), drops = matDrops(m);

  const shopsHtml = shops.length
    ? `<div class="tagbar">${shops.map(s=>`<span class="tag">${esc(s)}</span>`).join("")}</div>`
    : `<div class="empty" style="padding:14px">Not sold in any shop.</div>`;
  const areasHtml = areas.length
    ? `<div class="tagbar">${areas.map(a=>`<span class="tag">${esc(a.area)}${a.status ? ` &middot; ${esc(a.status)}` : ""}</span>`).join("")}</div>`
    : `<div class="empty" style="padding:14px">No area search data.</div>`;
  const dungeonsHtml = dungeons.map(d => `
      <div class="adv"><div><b>${esc(d.dungeon)}</b> <span class="race" style="color:var(--dim)">${esc(d.area)}</span></div>
        <div class="r">${d.floors} floor${d.floors>1?"s":""}</div></div>`).join("");
  const dropsHtml = drops.map(d => `
      <div class="adv" data-unit="${d.id}"><div><b>${esc(d.name)}</b></div>
        <div class="r">drops it</div></div>`).join("");
  const foundHtml = [
    dungeonsHtml ? `<h3 style="margin-top:12px">Dungeon rewards (${dungeons.length})</h3>${dungeonsHtml}` : "",
    dropsHtml ? `<h3 style="margin-top:12px">Dropped by (${drops.length} units)</h3>${dropsHtml}` : "",
  ].join("") || `<div class="empty" style="padding:14px">No dungeon or drop data.</div>`;

  const craftHtml = craft.map(c => `
      <div class="adv" data-craft="${esc(c.result)}">
        <div><b>${esc(c.result)}</b> <span class="race" style="color:var(--dim)">${esc(c.mold)}</span></div>
        <div class="r">${esc(c.ore)} + ${esc(c.item1)} + ${esc(c.item2)}<br>
          ${esc(c.effect)} &middot; <span class="${rateClass(c.success)}">${c.success}%</span></div>
      </div>`).join("") || `<div class="empty" style="padding:14px">Not used in any crafting recipe.</div>`;

  const grouped = new Map();
  emblems.forEach(e => {
    const g = grouped.get(e.emblem) || {name: e.emblem, n: 0, min: e.success, max: e.success};
    g.n++; g.min = Math.min(g.min, e.success); g.max = Math.max(g.max, e.success);
    grouped.set(e.emblem, g);
  });
  const embHtml = [...grouped.values()].map(g => `
      <div class="adv" data-emb="${esc(g.name)}">
        <div><b>${esc(g.name)}</b></div>
        <div class="r">${g.n} recipe${g.n > 1 ? "s" : ""} &middot;
          <span class="${rateClass(g.min)}">${g.min === g.max ? g.min + "%" : g.min + "-" + g.max + "%"}</span></div>
      </div>`).join("") || `<div class="empty" style="padding:14px">Not used in any emblem recipe.</div>`;

  $("modal-body").innerHTML = `
    <h2>${esc(m.name)}</h2>
    <div class="m-sub">${esc(m.category)} &middot; Rarity ${m.rarity}
      ${m.effect && m.effect !== "-" ? `&middot; ${esc(m.effect)}` : "&middot; no effect"}
      &middot; material #${m.id}</div>
    <div class="sect"><h3>Purchase in (${shops.length} location${shops.length===1?"":"s"})</h3>${shopsHtml}</div>
    <div class="sect"><h3>Area searches (${areas.length})</h3>${areasHtml}</div>
    <div class="sect"><h3>Where to find</h3>${foundHtml}</div>
    <div class="sect"><h3>Used in crafting (${craft.length})</h3>${craftHtml}</div>
    <div class="sect"><h3>Used in emblems (${grouped.size} emblems)</h3>${embHtml}</div>`;
  $("modal").classList.add("on"); $("backdrop").classList.add("on");
  $("modal-body").querySelectorAll(".adv[data-craft]").forEach(d=>d.onclick=()=>{
    closeModal(); showTab("crafting");
    $("kq").value = d.dataset.craft; $("ksort").value = "result"; renderCrafting();
    window.scrollTo({top:0, behavior:"smooth"});
  });
  $("modal-body").querySelectorAll(".adv[data-emb]").forEach(d=>d.onclick=()=>showEmblem(d.dataset.emb));
  $("modal-body").querySelectorAll(".adv[data-unit]").forEach(d=>d.onclick=()=>openDetail(+d.dataset.unit));
}

$("mcat").querySelectorAll(".chip").forEach(c=>c.onclick=()=>{
  $("mcat").querySelectorAll(".chip").forEach(x=>x.classList.remove("on")); c.classList.add("on"); renderMaterials(); });
[...new Set(MATERIALS.flatMap(m=>matShops(m)))].sort()
  .forEach(v=>{ const o=document.createElement("option"); o.textContent=v; $("mshop").appendChild(o); });
["mq","mmin","mmax","mshop","msort"].forEach(id=>$(id).addEventListener("input", renderMaterials));
$("mclear").onclick = () => {
  ["mq","mmin","mmax","mshop"].forEach(id=>$(id).value="");
  $("mcat").querySelectorAll(".chip").forEach((x,i)=>x.classList.toggle("on", i===0));
  $("msort").value="rarity"; renderMaterials();
};

// ---- crafting
const MOLD_ORDER = ["Sword","Spear","Axe","Claw","Blade","Bow","Staff","Mace","Armor","Accessories"];
[...new Set(CRAFTING.map(c=>c.mold))]
  .sort((a,b)=>MOLD_ORDER.indexOf(a)-MOLD_ORDER.indexOf(b))
  .forEach(v=>{ const o=document.createElement("option"); o.textContent=v; $("kmold").appendChild(o); });
[...new Set(CRAFTING.map(c=>c.ore))].sort()
  .forEach(v=>{ const o=document.createElement("option"); o.textContent=v; $("kore").appendChild(o); });
const EFFECT_NAME = Object.fromEntries(EFFECTS.map(e=>[e.id, e.name]));
const EFFECT_BEHAVIOR = Object.fromEntries(EFFECTS.filter(e=>e.behavior).map(e=>[e.id, e.behavior]));
const behaviorFor = ids => (ids||[]).map(i=>EFFECT_BEHAVIOR[i]).filter(Boolean).join(" + ");

$("fbody").innerHTML = EFFECTS.map(e=>
  `<tr><td class="eid">${e.id}</td><td>${esc(e.name)}</td>` +
  `<td class="race">${e.behavior ? esc(e.behavior) : "-"}</td></tr>`).join("");

function rateClass(s){ return s>=30?"rate30" : s>=20?"rate20" : s>=10?"rate10" : "rate5"; }

function filteredCraft(){
  const q=$("kq").value.trim().toLowerCase(), mold=$("kmold").value,
        ore=$("kore").value, max=+$("krate").value||0;
  return CRAFTING.filter(c=>{
    if (mold && c.mold!==mold) return false;
    if (ore && c.ore!==ore) return false;
    if (max && c.success>max) return false;
    if (q && !(c.result+" "+c.mold+" "+c.ore+" "+c.item1+" "+c.item2+" "+c.effect)
              .toLowerCase().includes(q)) return false;
    return true;
  });
}

function renderCrafting(){
  const key=$("ksort").value;
  const rows = filteredCraft().sort((a,b)=>{
    if (key==="success") return b.success-a.success || a.mold.localeCompare(b.mold);
    if (key==="mold")    return (MOLD_ORDER.indexOf(a.mold)-MOLD_ORDER.indexOf(b.mold)) || b.success-a.success;
    if (key==="ore")     return a.ore.localeCompare(b.ore) || b.success-a.success;
    return a.result.localeCompare(b.result);
  });
  $("kcount").textContent = `${rows.length} of ${CRAFTING.length} recipes`;
  $("kempty").style.display = rows.length ? "none" : "block";
  const tags = ["all molds"];
  if ($("kmold").value) tags.unshift($("kmold").value);
  if ($("kore").value) tags.push($("kore").value);
  if (+$("krate").value) tags.push(`<=${$("krate").value}% success`);
  $("ktags").innerHTML = tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("");
  $("kbody").innerHTML = rows.map(c=>{
    const eids = (c.effect_ids||[]).map(i=>`<span class="eid">#${i}</span>`).join(" ");
    const beh = behaviorFor(c.effect_ids);
    return `<tr>
      <td>${esc(c.mold)}</td><td>${esc(c.ore)}</td>
      <td>${esc(c.item1)}</td><td>${esc(c.item2)}</td>
      <td><b>${esc(c.result)}</b></td>
      <td>${esc(c.effect)} ${eids}${beh ? `<div class="sub">${esc(beh)}</div>` : ""}</td>
      <td class="${rateClass(c.success)}">${c.success}%</td></tr>`;
  }).join("");
}
["kq","kmold","kore","krate","ksort"].forEach(id=>$(id).addEventListener("input",renderCrafting));
$("kclear").onclick = () => { ["kq","kmold","kore","krate"].forEach(id=>$(id).value="");
  $("ksort").value="success"; renderCrafting(); };

renderEmblems(); renderMaterials(); renderUnits(); renderTeam(); renderCrafting();
</script>
</body>
</html>
"""


def build_html(units: list[dict], emblems: list[dict],
               crafting: list[dict], effects: list[dict],
               materials: list[dict]) -> str:
    return (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(units, separators=(",", ":")))
            .replace("__EMBLEMS__", json.dumps(emblems, separators=(",", ":")))
            .replace("__MATERIALS__", json.dumps(materials, separators=(",", ":")))
            .replace("__CRAFTING__", json.dumps(crafting, separators=(",", ":")))
            .replace("__EFFECTS__", json.dumps(effects, separators=(",", ":")))
            .replace("__INGALIAS__", json.dumps(INGREDIENT_ALIASES, separators=(",", ":")))
            .replace("__EFFECTCOUNT__", str(len(effects)))
            .replace("__MATCOUNT__", str(len(materials)))
            .replace("__COUNT__", str(len(units))))


# ------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--html", help="parse a local index HTML file instead of fetching")
    ap.add_argument("--details", action="store_true",
                    help="also fetch each unit page (ability + evolution); cached in raw/")
    ap.add_argument("--emblems", action="store_true",
                    help="also fetch the Emblem Database (recipes); cached in raw/")
    ap.add_argument("--crafting", action="store_true",
                    help="also fetch the crafting chart (weapons/armor/accessories); cached in raw/")
    ap.add_argument("--materials", action="store_true",
                    help="also fetch the Material Database (jewels/ores/other); cached in raw/")
    ap.add_argument("--material-details", action="store_true",
                    help="also fetch each material's page (purchase locations, drops, "
                         "area searches, dungeon rewards); cached in raw/; implies --materials")
    ap.add_argument("--rankup", action="store_true",
                    help="also fetch the guide's rankup chart: adds SP to units and "
                         "writes rankup.json/csv; cached in raw/")
    ap.add_argument("--out", default="unitdb", help="output dir (default: unitdb)")
    args = ap.parse_args()

    page = Path(args.html).read_text(encoding="utf-8", errors="replace") if args.html else fetch(args.url)
    units = parse_units(page)
    if not units:
        print("ERROR: no units parsed - page layout changed?", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.details:
        cache = out / "raw"
        ok = 0
        for i, u in enumerate(units, 1):
            fresh = not (cache / f"unit_{u['id']:03d}.html").exists()
            if fresh:
                time.sleep(0.4)  # be polite to archive.org
            try:
                detail = parse_detail(fetch_detail(u["id"], cache))
                u.update(detail)
                ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! unit {u['id']} ({u['name']}): {e}", file=sys.stderr, flush=True)
            if i % 20 == 0:
                print(f"  details {i}/{len(units)}", flush=True)
        missing = [u["id"] for u in units
                   if not (cache / f"unit_{u['id']:03d}.html").exists()]
        if missing:
            print(f"missing (re-run to retry): {missing}", flush=True)
        print(f"details fetched: {ok}/{len(units)}")

    # --- community guide (crafting chart, effect ids, rankup chart) ---
    guide_text: str | None = None
    if args.crafting or args.rankup:
        cached = out / "raw" / "crafting.txt"
        try:
            if cached.exists() and cached.stat().st_size > 1000:
                guide_text = cached.read_text(encoding="utf-8", errors="replace")
            else:
                guide_text = fetch(GIST_URL)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(guide_text, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"  ! guide fetch: {e}", file=sys.stderr)

    rankup: list[dict] = []
    if guide_text and args.rankup:
        rankup = parse_rankup(guide_text)
        with_sp = merge_sp(units, rankup)
        (out / "rankup.json").write_text(json.dumps(rankup, indent=2), encoding="utf-8")
        with (out / "rankup.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=RANKUP_FIELDS)
            w.writeheader()
            w.writerows(rankup)
        print(f"rankup: {len(rankup)} edges from the guide "
              f"({len({r['from'] for r in rankup})} source units), "
              f"SP known for {with_sp} units")
        cc = crosscheck_rankup(units, rankup)
        print(f"  cross-check vs scraped data: {cc['shared']} shared edges, "
              f"{cc['agree']} agree on rank/level/VP/emblem")
        for key, field, gval, sval in cc["diffs"]:
            print(f"    ! {key[0]} -> {key[1]}: guide {field}={gval}, scraped={sval}")
        for key in cc["only_guide"]:
            print(f"    + guide only: {key[0]} -> {key[1]}")
        for key in cc["only_scraped"]:
            print(f"    + scraped only: {key[0]} -> {key[1]}")

    (out / "units.json").write_text(json.dumps(units, indent=2), encoding="utf-8")

    with (out / "units.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for u in units:
            row = dict(u)
            row["advances"] = "; ".join(
                f"{a['name']} (rank {a['rank']}, lvl {a['level']}, {a['vp']} VP, {a['emblem']})"
                for a in u["advances"])
            w.writerow(row)

    emblems: list[dict] = []
    if args.emblems:
        cached = out / "raw" / "emblems.html"
        try:
            if cached.exists() and cached.stat().st_size > 1000:
                ehtml = cached.read_text(encoding="utf-8", errors="replace")
            else:
                ehtml = fetch(EMBLEM_URL)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(ehtml, encoding="utf-8")
            emblems = parse_emblems(ehtml)
            (out / "emblems.json").write_text(json.dumps(emblems, indent=2), encoding="utf-8")
            with (out / "emblems.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=EMBLEM_FIELDS)
                w.writeheader()
                w.writerows(emblems)
            print(f"emblems: {len(emblems)} recipes, "
                  f"{len({e['emblem'] for e in emblems})} distinct")
        except Exception as e:  # noqa: BLE001
            print(f"  ! emblems: {e}", file=sys.stderr)

    materials: list[dict] = []
    if args.materials or args.material_details:
        cached = out / "raw" / "materials.html"
        try:
            if cached.exists() and cached.stat().st_size > 1000:
                mhtml = cached.read_text(encoding="utf-8", errors="replace")
            else:
                mhtml = fetch(MATERIAL_URL)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(mhtml, encoding="utf-8")
            materials = parse_materials(mhtml)
            cats = {c: sum(1 for m in materials if m["category"] == c)
                    for c in dict.fromkeys(m["category"] for m in materials)}
            print(f"materials: {len(materials)} items "
                  f"({', '.join(f'{k} {v}' for k, v in cats.items())})")
        except Exception as e:  # noqa: BLE001
            print(f"  ! materials: {e}", file=sys.stderr)

    if args.material_details and materials:
        cache = out / "raw"
        ok = 0
        for i, m in enumerate(materials, 1):
            fresh = not (cache / f"material_{m['id']:03d}.html").exists()
            if fresh:
                time.sleep(0.4)  # be polite to archive.org
            try:
                m.update(parse_material_detail(fetch_material_detail(m["id"], cache)))
                ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! material {m['id']} ({m['name']}): {e}", file=sys.stderr, flush=True)
            if i % 20 == 0:
                print(f"  material details {i}/{len(materials)}", flush=True)
        missing = [m["id"] for m in materials
                   if not (cache / f"material_{m['id']:03d}.html").exists()]
        if missing:
            print(f"missing (re-run to retry): {missing}", flush=True)
        print(f"material details fetched: {ok}/{len(materials)}")

    if materials:
        (out / "materials.json").write_text(json.dumps(materials, indent=2), encoding="utf-8")
        with (out / "materials.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=MATERIAL_FIELDS)
            w.writeheader()
            for m in materials:
                row = dict(m)
                row["purchase_in"] = "; ".join(m.get("purchase_in", []))
                row["dropped_by"] = "; ".join(d["name"] for d in m.get("dropped_by", []))
                row["area_searches"] = "; ".join(
                    f'{a["area"]} ({a["status"]})' for a in m.get("area_searches", []))
                row["dungeon_reward"] = "; ".join(
                    f'{d["dungeon"]} / {d["area"]} (floors {d["floors"]})'
                    for d in m.get("dungeon_reward", []))
                w.writerow(row)

    crafting: list[dict] = []
    crafting_effects: list[dict] = []
    if args.crafting and guide_text:
        try:
            crafting, crafting_effects = parse_crafting(guide_text)
            (out / "crafting.json").write_text(json.dumps(crafting, indent=2), encoding="utf-8")
            with (out / "crafting.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=CRAFT_FIELDS)
                w.writeheader()
                for c in crafting:
                    row = dict(c)
                    row["effect_ids"] = "+".join(str(i) for i in c["effect_ids"])
                    w.writerow(row)
            (out / "effects.json").write_text(json.dumps(crafting_effects, indent=2), encoding="utf-8")
            with (out / "effects.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["id", "name", "behavior"])
                w.writeheader()
                w.writerows(crafting_effects)
            print(f"crafting: {len(crafting)} recipes across "
                  f"{len({c['mold'] for c in crafting})} molds, "
                  f"{len(crafting_effects)} effect ids")
        except Exception as e:  # noqa: BLE001
            print(f"  ! crafting: {e}", file=sys.stderr)

    app = out / "PocketKingdom-Units.html"
    app.write_text(build_html(units, emblems, crafting, crafting_effects, materials),
                   encoding="utf-8")

    print(f"units: {len(units)}")
    print(f"wrote {out/'units.json'}, {out/'units.csv'}, {app}")
    top = sorted([u for u in units if u["slots"] == 1], key=lambda u: -u["agi"])[:3]
    print("top AGI, 1-slot:", [(u["name"], u["agi"]) for u in top])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
