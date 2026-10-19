#!/usr/bin/env python3
"""Build a Pocket Kingdom unit database from the archived warcry.com unit index.

Source (Wayback Machine capture, 2005-02-10):
  http://pk.warcry.com/units/   ->  115 units with Class/Race/Rank/Slot/Move/stats

Outputs (default: ./unitdb/):
  units.json   structured records
  units.csv    spreadsheet-friendly
  PocketKingdom-Units.html   self-contained filterable app (data embedded)

The HTML app is generated with the data inlined so it works offline by simply
double-clicking the file (no server, no fetch/CORS issues).

Usage:
  python3 tools/build_unitdb.py                     # fetch + build
  python3 tools/build_unitdb.py --html cached.html  # parse a saved page
"""
from __future__ import annotations

import argparse
import csv
import html as htmlmod
import json
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://web.archive.org/web/20050210003854/"
    "http://pk.warcry.com/units/"
)

STATS = ["hp", "atk", "def", "agi", "dex", "wis", "int", "hit"]
FIELDS = ["id", "name", "race", "race_icon", "rank", "slots", "move", *STATS]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pk-unitdb/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace")


def _text(cell: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", cell)).strip()


def _int(s: str) -> int:
    m = re.search(r"-?\d+", s)
    return int(m.group()) if m else 0


def parse_units(page: str) -> list[dict]:
    rows = [
        r
        for r in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", page)
        if "view_unit.phtml?id=" in r
    ]
    units: list[dict] = []
    for row in rows:
        cells = re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)
        if len(cells) < 14:
            continue
        ids = re.search(r"view_unit\.phtml\?id=(\d+)", row)
        if not ids:
            continue
        icon = re.search(r"race_icons/(\d+)\.gif", cells[0]) or re.search(
            r"race_icons/(\d+)\.gif", row
        )
        alts = re.findall(r'alt="([^"]*)"', cells[4] + cells[5])
        slot_alt = next((a for a in alts if "Slot" in a), "")
        move = next((a for a in alts if a in ("Walk", "Fly")), "")
        nums = [_int(_text(cells[6 + i])) for i in range(8)]
        units.append(
            {
                "id": int(ids.group(1)),
                "name": _text(cells[1]),
                "race": _text(cells[2]),
                "race_icon": int(icon.group(1)) if icon else 0,
                "rank": _int(_text(cells[3])),
                "slots": _int(slot_alt) or 1,
                "move": move or "Walk",
                **dict(zip(STATS, nums)),
            }
        )
    units.sort(key=lambda u: u["id"])
    return units


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pocket Kingdom - Unit Database</title>
<style>
  :root{
    --bg:#12141a; --panel:#1b1e27; --panel2:#222634; --line:#333a4d;
    --txt:#e6e9f0; --dim:#98a0b3; --accent:#f0b429; --accent2:#4aa3ff;
    --good:#57d38c;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
       font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:16px 20px;border-bottom:1px solid var(--line);
         background:linear-gradient(180deg,#1e2230,#171a23)}
  h1{margin:0;font-size:18px;letter-spacing:.3px}
  h1 span{color:var(--accent)}
  .sub{color:var(--dim);font-size:12px;margin-top:4px}
  .wrap{padding:16px 20px 60px;max-width:1400px;margin:0 auto}
  .controls{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;
            background:var(--panel);border:1px solid var(--line);
            border-radius:10px;padding:14px}
  .fld{display:flex;flex-direction:column;gap:5px}
  .fld label{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--dim)}
  input,select{background:var(--panel2);border:1px solid var(--line);color:var(--txt);
               border-radius:7px;padding:7px 9px;font-size:13px;min-width:70px}
  input[type=number]{width:80px}
  input[type=search]{min-width:190px}
  .chips{display:flex;gap:6px}
  .chip{border:1px solid var(--line);background:var(--panel2);color:var(--dim);
        border-radius:999px;padding:6px 13px;cursor:pointer;font-size:13px;user-select:none}
  .chip.on{background:var(--accent);border-color:var(--accent);color:#20180a;font-weight:600}
  .btn{background:var(--accent2);border:none;color:#04121f;font-weight:600;
       border-radius:7px;padding:8px 14px;cursor:pointer;font-size:13px}
  .btn.ghost{background:transparent;border:1px solid var(--line);color:var(--dim);font-weight:500}
  .meta{display:flex;justify-content:space-between;align-items:center;
        margin:16px 2px 8px;color:var(--dim);font-size:12.5px}
  table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
  th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
  th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),
  th:nth-child(3),td:nth-child(3){text-align:left}
  thead th{position:sticky;top:0;background:#1a1d27;cursor:pointer;color:var(--dim);
           font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;z-index:2}
  thead th:hover{color:var(--txt)}
  thead th.sorted{color:var(--accent)}
  tbody tr:nth-child(odd){background:rgba(255,255,255,.015)}
  tbody tr:hover{background:rgba(74,163,255,.09)}
  tbody tr.top{background:rgba(240,180,41,.13)}
  .name{font-weight:600}
  .race{color:var(--dim)}
  .best{color:var(--good);font-weight:700}
  .stat{position:relative}
  .slot1{color:var(--good)}
  .slot2{color:var(--accent)}
  .slot3{color:#ff8f6b}
  .empty{padding:40px;text-align:center;color:var(--dim)}
  .tagbar{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .tag{font-size:11px;color:var(--dim);border:1px solid var(--line);
       border-radius:6px;padding:2px 7px}
  a{color:var(--accent2)}
  footer{color:#5c6478;font-size:11.5px;padding:0 20px 40px;max-width:1400px;margin:0 auto}
</style>
</head>
<body>
<header>
  <h1>Pocket Kingdom <span>Unit Database</span></h1>
  <div class="sub">__COUNT__ units &middot; source: pk.warcry.com (Wayback Machine, 2005-02-10) &middot; offline, data embedded</div>
</header>
<div class="wrap">
  <div class="controls">
    <div class="fld">
      <label>Search</label>
      <input id="q" type="search" placeholder="name or race...">
    </div>
    <div class="fld">
      <label>Race</label>
      <select id="race"><option value="">All</option></select>
    </div>
    <div class="fld">
      <label>Move</label>
      <select id="move">
        <option value="">Any</option><option>Walk</option><option>Fly</option>
      </select>
    </div>
    <div class="fld">
      <label>Slots</label>
      <div class="chips" id="slots">
        <span class="chip on" data-v="0">Any</span>
        <span class="chip" data-v="1">1</span>
        <span class="chip" data-v="2">2</span>
        <span class="chip" data-v="3">3</span>
      </div>
    </div>
    <div class="fld">
      <label>Rank min-max</label>
      <div style="display:flex;gap:6px;align-items:center">
        <input id="rmin" type="number" min="1" max="9" placeholder="1">
        <span style="color:var(--dim)">-</span>
        <input id="rmax" type="number" min="1" max="9" placeholder="9">
      </div>
    </div>
    <div class="fld">
      <label>Rank by</label>
      <select id="sort"></select>
    </div>
    <div class="fld">
      <label>&nbsp;</label>
      <button class="btn ghost" id="reset">Reset</button>
    </div>
  </div>

  <div class="meta">
    <div id="count"></div>
    <div class="tagbar" id="best"></div>
  </div>

  <table>
    <thead><tr id="head"></tr></thead>
    <tbody id="body"></tbody>
  </table>
  <div class="empty" id="empty" style="display:none">No units match these filters.</div>
</div>
<footer>
  Stats are base values from the 2005 warcry.com capture; the retail game scales
  HP/stats with level, and combine/evolution changes them. HP is the base value shown
  in the index. Not affiliated with Nokia / the game's rights holders.
</footer>

<script>
const UNITS = __DATA__;
const STATS = ["hp","atk","def","agi","dex","wis","int","hit"];
const COLS = [
  ["id","#"],["name","Class"],["race","Race"],["rank","Rank"],["slots","Slots"],
  ["move","Move"],...STATS.map(s=>[s,s.toUpperCase()])
];
let sortKey="agi", sortDir=-1;

const $=id=>document.getElementById(id);

// populate dropdowns
[...new Set(UNITS.map(u=>u.race))].sort().forEach(r=>{
  const o=document.createElement("option"); o.textContent=r; $("race").appendChild(o);
});
COLS.forEach(([k,label])=>{
  const o=document.createElement("option"); o.value=k; o.textContent=label; $("sort").appendChild(o);
});
$("sort").value="agi";

// header
$("head").innerHTML = COLS.map(([k,l])=>`<th data-k="${k}">${l}</th>`).join("");
$("head").querySelectorAll("th").forEach(th=>{
  th.onclick=()=>{ const k=th.dataset.k;
    if(sortKey===k) sortDir=-sortDir; else { sortKey=k; sortDir = (k==="name"||k==="race"||k==="move")?1:-1; }
    render(); };
});

// slot chips
$("slots").querySelectorAll(".chip").forEach(c=>{
  c.onclick=()=>{ $("slots").querySelectorAll(".chip").forEach(x=>x.classList.remove("on"));
    c.classList.add("on"); render(); };
});

["q","race","move","rmin","rmax"].forEach(id=>$(id).addEventListener("input",render));
$("reset").onclick=()=>{ $("q").value=""; $("race").value=""; $("move").value="";
  $("rmin").value=""; $("rmax").value=""; $("sort").value="agi"; sortKey="agi"; sortDir=-1;
  $("slots").querySelectorAll(".chip").forEach((x,i)=>x.classList.toggle("on", i===0)); render(); };

function activeSlots(){ const c=$("slots").querySelector(".chip.on"); return +c.dataset.v; }

function filtered(){
  const q=$("q").value.trim().toLowerCase();
  const race=$("race").value, move=$("move").value, sl=activeSlots();
  const rmin=+$("rmin").value||0, rmax=+$("rmax").value||99;
  return UNITS.filter(u=>{
    if(q && !(u.name.toLowerCase().includes(q)||u.race.toLowerCase().includes(q))) return false;
    if(race && u.race!==race) return false;
    if(move && u.move!==move) return false;
    if(sl && u.slots!==sl) return false;
    if(u.rank<rmin||u.rank>rmax) return false;
    return true;
  });
}

function render(){
  const rows=filtered().sort((a,b)=>{
     const x=a[sortKey],y=b[sortKey];
     if(typeof x==="string") return sortDir*x.localeCompare(y);
     return sortDir*(x-y);
  });
  $("head").querySelectorAll("th").forEach(th=>th.classList.toggle("sorted", th.dataset.k===sortKey));

  $("count").textContent = `${rows.length} of ${UNITS.length} units`;
  $("empty").style.display = rows.length?"none":"block";

  // best value per numeric column among filtered rows
  const best={};
  STATS.forEach(s=>{ best[s]=rows.length?Math.max(...rows.map(r=>r[s])):null; });

  // context tags
  const tags=[];
  if(activeSlots()) tags.push(`${activeSlots()}-slot only`);
  if($("move").value) tags.push($("move").value);
  if($("race").value) tags.push($("race").value);
  if(!tags.length) tags.push("all units");
  $("best").innerHTML = tags.map(t=>`<span class="tag">${t}</span>`).join("") +
     (rows.length?`<span class="tag">best ${sortKey.toUpperCase()}: <b style="color:var(--good)">${best[sortKey]??""}</b></span>`:"");

  $("body").innerHTML = rows.map(u=>{
    const cells=COLS.map(([k])=>{
      if(k==="name") return `<td><span class="name">${u.name}</span></td>`;
      if(k==="race") return `<td><span class="race">${u.race}</span></td>`;
      if(k==="slots") return `<td class="slot${u.slots}">${u.slots}</td>`;
      if(STATS.includes(k)){ const b=best[k]===u[k]&&rows.length>1?` class="stat best"`:"";
        return `<td${b}>${u[k]}</td>`; }
      return `<td>${u[k]}</td>`;
    }).join("");
    return `<tr data-id="${u.id}">${cells}</tr>`;
  }).join("");
}

render();
</script>
</body>
</html>
"""


def build_html(units: list[dict]) -> str:
    return (
        HTML_TEMPLATE.replace("__DATA__", json.dumps(units, separators=(",", ":")))
        .replace("__COUNT__", str(len(units)))
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--html", help="parse a local HTML file instead of fetching")
    ap.add_argument("--out", default="unitdb", help="output directory (default: unitdb)")
    args = ap.parse_args()

    page = Path(args.html).read_text(encoding="utf-8", errors="replace") if args.html else fetch(args.url)
    units = parse_units(page)
    if not units:
        print("ERROR: no units parsed - page layout changed?", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "units.json").write_text(json.dumps(units, indent=2), encoding="utf-8")

    with (out / "units.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(units)

    app = out / "PocketKingdom-Units.html"
    app.write_text(build_html(units), encoding="utf-8")

    print(f"units: {len(units)}")
    print(f"wrote {out/'units.json'}, {out/'units.csv'}, {app}")
    top_agi_1 = sorted([u for u in units if u["slots"] == 1], key=lambda u: -u["agi"])[:3]
    print("top AGI, 1-slot:", [(u["name"], u["agi"]) for u in top_agi_1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
