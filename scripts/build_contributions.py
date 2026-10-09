#!/usr/bin/env python3
"""Render the profile contributions panel as SVG from GitHub's public calendar.

Usage: build_contributions.py [--user NAME] [--out DIR] [--html FILE]

Reads the public contributions calendar (no token needed) and writes
contributions-dark.svg and contributions-light.svg into DIR. Every number is
computed from that calendar. If the fetch or parse fails, nothing is written
and the exit code is non-zero, so a stale image is never replaced by a guess.
"""
import argparse
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

GAP = 3
LEFT, TOP_PAD, WIDTH = 56, 28, 760
HEAT_TOP = 178
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "dark": dict(
        bg="#1a1b27", border="#2b2d3f", title="#c0caf5", text="#8a92b8", muted="#5b6285",
        divider="#2b2d3f", levels=["#252840", "#2c5a8a", "#3d85b8", "#4fb3c8", "#7ee8d1"],
        grad=("#70a5fd", "#7ee8d1"), today="#bf91f3", glow=True),
    "light": dict(
        bg="#ffffff", border="#d0d7de", title="#1f2328", text="#57606a", muted="#8c959f",
        divider="#d8dee4", levels=["#eaeef2", "#bcd8f3", "#7fb2e6", "#3f86d4", "#1a56a8"],
        grad=("#2563eb", "#0d9488"), today="#8250df", glow=False),
}


@dataclass
class Day:
    day: date
    level: int
    count: int


def fetch(user: str) -> str:
    url = f"https://github.com/users/{user}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-builder"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse(html: str) -> list[Day]:
    cells = re.findall(
        r'data-date="(\d{4}-\d{2}-\d{2})"\s+id="(contribution-day-component-\d+-\d+)"\s+data-level="(\d)"', html)
    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="(contribution-day-component-[^"]+)"[^>]*>([^<]*)</tool-tip>', html))
    days = []
    for iso, cid, level in cells:
        m = re.match(r"\s*(\d+) contributions?", tips.get(cid, ""))
        days.append(Day(date.fromisoformat(iso), int(level), int(m.group(1)) if m else 0))
    days.sort(key=lambda d: d.day)
    if len(days) < 300:
        raise ValueError(f"expected ~371 calendar cells, parsed {len(days)}")
    if not any(d.count for d in days) and any(d.level for d in days):
        raise ValueError("calendar has activity levels but no counts; page format changed")
    return days


def stats(days: list[Day]) -> dict:
    longest = run = 0
    for d in days:
        run = run + 1 if d.count else 0
        longest = max(longest, run)
    current, idx = 0, len(days) - 1
    if idx >= 0 and days[idx].count == 0:  # today may not have activity yet
        idx -= 1
    while idx >= 0 and days[idx].count:
        current += 1
        idx -= 1
    return dict(total=sum(d.count for d in days), active=sum(1 for d in days if d.count),
                current=current, longest=longest, start=days[0].day, end=days[-1].day)


def fmt(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def render(days: list[Day], s: dict, t: dict, name: str) -> str:
    first_sunday = days[0].day - timedelta(days=(days[0].day.weekday() + 1) % 7)
    cols = (days[-1].day - first_sunday).days // 7 + 1
    pitch = round((WIDTH - LEFT - TOP_PAD + GAP) / cols, 3)  # grid spans exactly margin to margin
    cell = round(pitch - GAP, 3)
    height = HEAT_TOP + 7 * pitch + 52
    grid_w = cols * pitch - GAP
    x0 = LEFT
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
      f'role="img" aria-labelledby="t d" font-family="{FONT}">')
    a(f'<title id="t">Contribution activity</title><desc id="d">{s["total"]} contributions on {s["active"]} active days '
      f'between {fmt(s["start"])} and {fmt(s["end"])}. Current streak {s["current"]} days, longest streak {s["longest"]} days.</desc>')
    g0, g1 = t["grad"]
    a(f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{g0}"/>'
      f'<stop offset="1" stop-color="{g1}"/></linearGradient>')
    if t["glow"]:
        a('<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4" result="b"/>'
          '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    a('</defs>')
    a(f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="14" fill="{t["bg"]}" stroke="{t["border"]}"/>')
    a(f'<rect x="{TOP_PAD}" y="26" width="4" height="18" rx="2" fill="url(#g)"/>')
    a(f'<text x="{TOP_PAD + 14}" y="41" font-size="17" font-weight="700" fill="{t["title"]}">Contributions</text>')
    a(f'<text x="{WIDTH - TOP_PAD}" y="41" font-size="13" text-anchor="end" fill="{t["text"]}">'
      f'{fmt(s["start"])} – {fmt(s["end"])}</text>')
    blocks = [(s["total"], "contributions"), (s["active"], "active days"),
              (s["current"], "day current streak"), (s["longest"], "day longest streak")]
    bw = (WIDTH - 2 * TOP_PAD) / 4
    for i, (num, label) in enumerate(blocks):
        bx = TOP_PAD + i * bw
        a(f'<text x="{bx:.0f}" y="102" font-size="38" font-weight="800" fill="url(#g)">{num}</text>')
        a(f'<text x="{bx:.0f}" y="126" font-size="14" fill="{t["text"]}">{label}</text>')
    a(f'<line x1="{TOP_PAD}" y1="146" x2="{WIDTH - TOP_PAD}" y2="146" stroke="{t["divider"]}"/>')

    last_m, last_x = None, -99
    for c in range(cols):
        d = first_sunday + timedelta(days=7 * c)
        if d.month != last_m and c - last_x >= 3 and c <= cols - 2:
            a(f'<text x="{x0 + c * pitch}" y="{HEAT_TOP - 9}" font-size="12" fill="{t["muted"]}">{d.strftime("%b")}</text>')
            last_x = c
        last_m = d.month
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text x="{TOP_PAD}" y="{HEAT_TOP + row * pitch + cell - 1}" font-size="12" fill="{t["muted"]}">{label}</text>')

    lv = t["levels"]
    base, glow = [], []
    for d in days:
        col = (d.day - first_sunday).days // 7
        row = (d.day.weekday() + 1) % 7
        x, y = x0 + col * pitch, HEAT_TOP + row * pitch
        rect = f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{lv[d.level]}"'
        if d.day == s["end"]:
            rect += f' stroke="{t["today"]}" stroke-width="1.5"'
        (glow if (t["glow"] and d.level >= 2) else base).append(rect + "/>")
    a("<g>" + "".join(base) + "</g>")
    if glow:
        a('<g filter="url(#glow)">' + "".join(glow) + "</g>")

    fy = HEAT_TOP + 7 * pitch + 24
    a(f'<text x="{TOP_PAD}" y="{fy}" font-size="12" fill="{t["muted"]}">{name} · updated {fmt(s["end"])}</text>')
    lx = x0 + grid_w - (5 * pitch + 70)
    a(f'<text x="{lx - 6}" y="{fy}" font-size="12" text-anchor="end" fill="{t["muted"]}">Less</text>')
    for i in range(5):
        a(f'<rect x="{lx + i * pitch}" y="{fy - 10}" width="{cell}" height="{cell}" rx="3" fill="{lv[i]}"/>')
    a(f'<text x="{lx + 5 * pitch + 4}" y="{fy}" font-size="12" fill="{t["muted"]}">More</text>')
    a("</svg>")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--user", default="ubaidurrehman-developer")
    p.add_argument("--out", default="assets")
    p.add_argument("--html", help="parse this saved calendar HTML instead of fetching")
    args = p.parse_args()
    try:
        html = Path(args.html).read_text(encoding="utf-8") if args.html else fetch(args.user)
        days = parse(html)
    except Exception as e:  # leave existing images untouched
        print(f"error: {e}", file=sys.stderr)
        return 1
    s = stats(days)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (out / f"contributions-{name}.svg").write_text(render(days, s, theme, args.user), encoding="utf-8")
    print({k: (str(v) if isinstance(v, date) else v) for k, v in s.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
