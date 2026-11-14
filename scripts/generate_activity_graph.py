#!/usr/bin/env python3
"""Generate a self-hosted GitHub activity SVG for the profile README.

The source is the public contribution calendar API. The SVG is committed to
the repository so the README does not depend on a third-party image renderer.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

USERNAME = "MokuLakshithReddy"
API_URL = f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y=last"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "activity-graph.svg"

WIDTH = 1000
HEIGHT = 300
MARGIN_LEFT = 64
MARGIN_RIGHT = 28
MARGIN_TOP = 66
MARGIN_BOTTOM = 48


def fetch_daily_contributions() -> dict[date, int]:
    request = Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "MokuLakshithReddy-Profile-Activity-Graph/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Contribution API returned HTTP {response.status}")
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not fetch GitHub contribution data: {exc}") from exc

    rows = payload.get("contributions")
    if not isinstance(rows, list) or len(rows) < 300:
        raise RuntimeError("Contribution API returned incomplete or unexpected data")

    daily: dict[date, int] = {}
    for row in rows:
        try:
            day = date.fromisoformat(row["date"])
            count = int(row["count"])
        except (KeyError, TypeError, ValueError):
            continue
        if count < 0:
            continue
        daily[day] = count

    if len(daily) < 300:
        raise RuntimeError("Contribution data did not contain enough valid daily entries")
    return daily


def build_svg(daily: dict[date, int]) -> str:
    today_utc = datetime.now(timezone.utc).date()
    latest = min(max(daily), today_utc)
    first = latest - timedelta(days=364)

    days = [first + timedelta(days=i) for i in range(365)]
    counts = [daily.get(day, 0) for day in days]
    total = sum(counts)
    peak = max(counts, default=0)
    y_max = max(4, int(math.ceil(max(peak, 1) / 4.0) * 4))

    plot_width = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    baseline = MARGIN_TOP + plot_height

    def x_at(index: int) -> float:
        return MARGIN_LEFT + (index / (len(days) - 1)) * plot_width

    def y_at(value: int) -> float:
        return MARGIN_TOP + plot_height - (value / y_max) * plot_height

    line_points = [
        f"{x_at(i):.2f},{y_at(value):.2f}" for i, value in enumerate(counts)
    ]
    line_path = "M " + " L ".join(line_points)
    area_path = (
        f"M {x_at(0):.2f},{baseline:.2f} "
        + " L ".join(line_points)
        + f" L {x_at(len(days)-1):.2f},{baseline:.2f} Z"
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-labelledby="graph-title graph-desc">',
        '<title id="graph-title">GitHub activity for MokuLakshithReddy</title>',
        (
            '<desc id="graph-desc">'
            f'{total:,} contributions between {first.isoformat()} and '
            f'{latest.isoformat()}. Daily contribution activity.'
            '</desc>'
        ),
        '<defs><linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0%" stop-color="#39c66f" stop-opacity="0.62"/>',
        '<stop offset="100%" stop-color="#39c66f" stop-opacity="0.035"/>',
        '</linearGradient></defs>',
        '<rect width="1000" height="300" rx="12" fill="#0d1117"/>',
        '<text x="30" y="34" fill="#58a6ff" font-size="21" '
        'font-family="Segoe UI,Arial,sans-serif" font-weight="600">'
        'GitHub Activity</text>',
        (
            f'<text x="970" y="34" text-anchor="end" fill="#8b949e" '
            f'font-size="13" font-family="Segoe UI,Arial,sans-serif">'
            f'{total:,} contributions · Last 12 months</text>'
        ),
    ]

    for tick in range(5):
        value = (y_max / 4) * tick
        y = y_at(int(value))
        parts.append(
            f'<line x1="{MARGIN_LEFT}" y1="{y:.2f}" x2="{WIDTH-MARGIN_RIGHT}" '
            f'y2="{y:.2f}" stroke="#30363d" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{MARGIN_LEFT-12}" y="{y+4:.2f}" text-anchor="end" '
            f'fill="#8b949e" font-size="11" '
            f'font-family="Segoe UI,Arial,sans-serif">{int(value)}</text>'
        )

    parts.extend([
        f'<path d="{area_path}" fill="url(#activity-fill)"/>',
        f'<path d="{line_path}" fill="none" stroke="#3fbf70" '
        'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>',
    ])

    last_month = None
    for index, day in enumerate(days):
        if day.day == 1 or index == 0:
            month_key = (day.year, day.month)
            if month_key != last_month:
                x = x_at(index)
                parts.append(
                    f'<line x1="{x:.2f}" y1="{baseline}" x2="{x:.2f}" '
                    f'y2="{baseline+5}" stroke="#8b949e" stroke-width="1"/>'
                )
                parts.append(
                    f'<text x="{x:.2f}" y="{baseline+23}" text-anchor="middle" '
                    f'fill="#8b949e" font-size="11" '
                    f'font-family="Segoe UI,Arial,sans-serif">'
                    f'{escape(day.strftime("%b %y"))}</text>'
                )
                last_month = month_key

    parts.extend([
        f'<text x="{MARGIN_LEFT}" y="{HEIGHT-9}" fill="#6e7681" '
        'font-size="10" font-family="Segoe UI,Arial,sans-serif">'
        f'{first.isoformat()}</text>',
        f'<text x="{WIDTH-MARGIN_RIGHT}" y="{HEIGHT-9}" text-anchor="end" '
        'fill="#6e7681" font-size="10" '
        'font-family="Segoe UI,Arial,sans-serif">'
        f'{latest.isoformat()}</text>',
        '</svg>',
    ])
    return "\n".join(parts) + "\n"


def main() -> int:
    try:
        daily = fetch_daily_contributions()
        svg = build_svg(daily)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(svg, encoding="utf-8")
        print(f"Updated {OUTPUT} from {len(daily)} daily contribution records.")
        return 0
    except Exception as exc:  # Fail safely; do not overwrite the existing graph.
        print(f"Activity graph update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
