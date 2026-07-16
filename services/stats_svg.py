"""Render canonical Stats as an embeddable SVG card (README-friendly).

Cached aggressively: responses set ``Cache-Control: public, max-age=86400``.
"""

from __future__ import annotations

import html
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from fastapi.responses import Response

SVG_CACHE_SECONDS = 86400
SVG_CACHE_CONTROL = f"public, max-age={SVG_CACHE_SECONDS}, s-maxage={SVG_CACHE_SECONDS}"

# Platform accents mirror routes/docs.py
PLATFORM_ACCENTS: Dict[str, str] = {
    "leetcode": "#ffa116",
    "codeforces": "#4f8df7",
    "codechef": "#c98a5e",
    "gfg": "#2f8d46",
    "hackerrank": "#1ec773",
    "github": "#3fb950",
    "tuf": "#ff7a3d",
}

PLATFORM_TITLES: Dict[str, str] = {
    "leetcode": "LeetCode",
    "codeforces": "Codeforces",
    "codechef": "CodeChef",
    "gfg": "GeeksforGeeks",
    "hackerrank": "HackerRank",
    "github": "GitHub",
    "tuf": "takeUforward",
}

# Preferred order + display labels for byDifficulty keys
DIFFICULTY_META: Dict[str, Tuple[str, str]] = {
    "easy": ("Easy", "#00b8a3"),
    "medium": ("Medium", "#ffc01e"),
    "hard": ("Hard", "#ff375f"),
    "basic": ("Basic", "#2db55d"),
    "school": ("School", "#8bc34a"),
    "fundamental": ("Fundamental", "#4caf50"),
    "commits": ("Commits", "#3fb950"),
    "prs": ("PRs", "#a371f7"),
    "issues": ("Issues", "#f85149"),
    "reviews": ("Reviews", "#58a6ff"),
}

TOTAL_LABELS: Dict[str, str] = {
    "github": "Total Commits",
}

THEMES = {
    "dark": {
        "bg": "#0a0a0c",
        "panel": "#121214",
        "border": "#1f1f22",
        "ink": "#fafafa",
        "muted": "#9b9ba4",
        "faint": "#6b6b73",
        "bar_track": "#1f1f22",
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "border": "#d0d7de",
        "ink": "#1f2328",
        "muted": "#656d76",
        "faint": "#8c959f",
        "bar_track": "#eaeef2",
    },
}


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _stats_dict(stats: Any) -> Dict[str, Any]:
    if stats is None:
        return {}
    if isinstance(stats, Mapping):
        return dict(stats)
    if hasattr(stats, "model_dump"):
        return stats.model_dump()
    if is_dataclass(stats) and not isinstance(stats, type):
        return asdict(stats)
    if hasattr(stats, "__dict__"):
        return {
            key: getattr(stats, key)
            for key in (
                "totalSolved",
                "totalQuestions",
                "acceptanceRate",
                "byDifficulty",
                "topicAnalysis",
            )
            if hasattr(stats, key)
        }
    return {}


def _topic_pairs(raw: Any) -> List[Tuple[str, int]]:
    pairs: List[Tuple[str, int]] = []
    if not raw:
        return pairs
    for item in raw:
        if isinstance(item, Mapping):
            topic = item.get("topic") or item.get("name") or ""
            count = int(item.get("count") or 0)
        else:
            topic = getattr(item, "topic", None) or getattr(item, "name", "") or ""
            count = int(getattr(item, "count", 0) or 0)
        if topic:
            pairs.append((str(topic), count))
    return pairs


def _difficulty_rows(by_difficulty: Mapping[str, Any], accent: str) -> List[Tuple[str, int, str]]:
    if not by_difficulty:
        return []
    rows: List[Tuple[str, int, str]] = []
    seen = set()
    for key in DIFFICULTY_META:
        if key in by_difficulty:
            label, color = DIFFICULTY_META[key]
            rows.append((label, int(by_difficulty.get(key) or 0), color))
            seen.add(key)
    for key, value in by_difficulty.items():
        if key in seen:
            continue
        label = str(key).replace("_", " ").title()
        rows.append((label, int(value or 0), accent))
    # Drop all-zero rows only when there are other non-zero rows
    if any(count > 0 for _, count, _ in rows):
        rows = [row for row in rows if row[1] > 0] or rows
    return rows[:6]


def _fmt_num(value: Optional[Union[int, float]]) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.1f}"
    return f"{int(value):,}"


def render_stats_svg(
    platform: str,
    username: str,
    stats: Any,
    *,
    accent: Optional[str] = None,
    theme: str = "dark",
    title: Optional[str] = None,
) -> str:
    """Build an SVG card from canonical Stats data."""
    platform_key = (platform or "").lower()
    accent_color = accent or PLATFORM_ACCENTS.get(platform_key, "#ffa116")
    platform_title = title or PLATFORM_TITLES.get(platform_key, platform_key.title() or "Stats")
    colors = THEMES.get((theme or "dark").lower(), THEMES["dark"])

    data = _stats_dict(stats)
    total_solved = int(data.get("totalSolved") or 0)
    total_questions = data.get("totalQuestions")
    acceptance = data.get("acceptanceRate")
    by_difficulty = data.get("byDifficulty") or {}
    if not isinstance(by_difficulty, Mapping):
        by_difficulty = {}
    topics = _topic_pairs(data.get("topicAnalysis"))
    diff_rows = _difficulty_rows(by_difficulty, accent_color)
    total_label = TOTAL_LABELS.get(platform_key, "Total Solved")

    width = 420
    pad_x = 22
    y = 28
    lines: List[str] = []

    # Header
    lines.append(
        f'<text x="{pad_x}" y="{y}" fill="{_escape(accent_color)}" font-size="13" '
        f'font-weight="700" font-family="ui-monospace,SFMono-Regular,Menlo,monospace">'
        f'{_escape(platform_title)} Stats</text>'
    )
    lines.append(
        f'<text x="{width - pad_x}" y="{y}" fill="{_escape(colors["muted"])}" font-size="12" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="end">'
        f'@{_escape(username)}</text>'
    )
    y += 18
    lines.append(
        f'<line x1="{pad_x}" y1="{y}" x2="{width - pad_x}" y2="{y}" '
        f'stroke="{_escape(colors["border"])}" stroke-width="1"/>'
    )
    y += 28

    # Total solved
    lines.append(
        f'<text x="{pad_x}" y="{y}" fill="{_escape(colors["faint"])}" font-size="11" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
        f'letter-spacing="0.06em">{_escape(total_label.upper())}</text>'
    )
    y += 26
    total_text = _fmt_num(total_solved)
    if total_questions is not None:
        total_text = f"{_fmt_num(total_solved)} / {_fmt_num(total_questions)}"
    lines.append(
        f'<text x="{pad_x}" y="{y}" fill="{_escape(colors["ink"])}" font-size="28" '
        f'font-weight="700" font-family="Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
        f'{_escape(total_text)}</text>'
    )

    meta_x = width - pad_x
    meta_y = y - 10
    if acceptance is not None:
        lines.append(
            f'<text x="{meta_x}" y="{meta_y}" fill="{_escape(colors["muted"])}" font-size="11" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="end">'
            f'Acceptance</text>'
        )
        lines.append(
            f'<text x="{meta_x}" y="{meta_y + 18}" fill="{_escape(accent_color)}" font-size="16" '
            f'font-weight="600" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="end">'
            f'{_escape(_fmt_num(float(acceptance)))}%</text>'
        )

    y += 22

    # Difficulty bars
    if diff_rows:
        y += 8
        max_count = max((count for _, count, _ in diff_rows), default=1) or 1
        bar_x = pad_x + 78
        bar_w = width - pad_x - bar_x - 52
        for label, count, color in diff_rows:
            lines.append(
                f'<text x="{pad_x}" y="{y + 11}" fill="{_escape(colors["muted"])}" font-size="12" '
                f'font-family="Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
                f'{_escape(label)}</text>'
            )
            lines.append(
                f'<rect x="{bar_x}" y="{y + 2}" width="{bar_w}" height="10" rx="3" '
                f'fill="{_escape(colors["bar_track"])}"/>'
            )
            fill_w = max(3, int(bar_w * (count / max_count))) if count else 0
            if fill_w:
                lines.append(
                    f'<rect x="{bar_x}" y="{y + 2}" width="{fill_w}" height="10" rx="3" '
                    f'fill="{_escape(color)}"/>'
                )
            lines.append(
                f'<text x="{width - pad_x}" y="{y + 11}" fill="{_escape(colors["ink"])}" font-size="12" '
                f'font-weight="600" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="end">'
                f'{_escape(_fmt_num(count))}</text>'
            )
            y += 22
        y += 4

    # Top topics
    top_topics = topics[:5]
    if top_topics:
        y += 10
        lines.append(
            f'<text x="{pad_x}" y="{y}" fill="{_escape(colors["faint"])}" font-size="11" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" letter-spacing="0.06em">'
            f'TOP TOPICS</text>'
        )
        y += 16
        max_topic = max((count for _, count in top_topics), default=1) or 1
        bar_x = pad_x + 148
        bar_w = width - pad_x - bar_x - 48
        for topic, count in top_topics:
            short = topic if len(topic) <= 18 else topic[:16] + "…"
            lines.append(
                f'<text x="{pad_x}" y="{y + 10}" fill="{_escape(colors["muted"])}" font-size="11" '
                f'font-family="Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
                f'{_escape(short)}</text>'
            )
            lines.append(
                f'<rect x="{bar_x}" y="{y + 1}" width="{bar_w}" height="8" rx="3" '
                f'fill="{_escape(colors["bar_track"])}"/>'
            )
            fill_w = max(3, int(bar_w * (count / max_topic))) if count else 0
            if fill_w:
                lines.append(
                    f'<rect x="{bar_x}" y="{y + 1}" width="{fill_w}" height="8" rx="3" '
                    f'fill="{_escape(accent_color)}" opacity="0.85"/>'
                )
            lines.append(
                f'<text x="{width - pad_x}" y="{y + 10}" fill="{_escape(colors["ink"])}" font-size="11" '
                f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" text-anchor="end">'
                f'{_escape(_fmt_num(count))}</text>'
            )
            y += 18

    height = y + 22
    body = "\n  ".join(lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_escape(platform_title)} stats for {_escape(username)}">'
        f"\n  <title>{_escape(platform_title)} Stats — {_escape(username)}</title>\n"
        f'  <rect width="100%" height="100%" rx="8" fill="{_escape(colors["bg"])}" '
        f'stroke="{_escape(colors["border"])}" stroke-width="1"/>\n'
        f"  {body}\n"
        f"</svg>"
    )


def render_error_svg(
    message: str,
    *,
    platform: str = "",
    username: str = "",
    accent: Optional[str] = None,
    theme: str = "dark",
) -> str:
    platform_key = (platform or "").lower()
    accent_color = accent or PLATFORM_ACCENTS.get(platform_key, "#f85149")
    colors = THEMES.get((theme or "dark").lower(), THEMES["dark"])
    width, height = 420, 120
    title = PLATFORM_TITLES.get(platform_key, "Stats")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Error">'
        f"\n  <title>Error loading stats</title>\n"
        f'  <rect width="100%" height="100%" rx="8" fill="{_escape(colors["bg"])}" '
        f'stroke="{_escape(colors["border"])}" stroke-width="1"/>\n'
        f'  <text x="22" y="36" fill="{_escape(accent_color)}" font-size="13" font-weight="700" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace">{_escape(title)} Stats</text>\n'
        f'  <text x="22" y="68" fill="{_escape(colors["ink"])}" font-size="14" '
        f'font-family="Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
        f'{_escape(message or "Failed to load stats")}</text>\n'
        f'  <text x="22" y="92" fill="{_escape(colors["muted"])}" font-size="12" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace">@{_escape(username)}</text>\n'
        f"</svg>"
    )


def stats_svg_response(
    platform: str,
    username: str,
    stats: Any,
    *,
    accent: Optional[str] = None,
    theme: str = "dark",
    title: Optional[str] = None,
    status_code: int = 200,
) -> Response:
    svg = render_stats_svg(
        platform,
        username,
        stats,
        accent=accent,
        theme=theme,
        title=title,
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        status_code=status_code,
        headers={
            "Cache-Control": SVG_CACHE_CONTROL,
            "Content-Type": "image/svg+xml; charset=utf-8",
        },
    )


def error_svg_response(
    message: str,
    *,
    platform: str = "",
    username: str = "",
    accent: Optional[str] = None,
    theme: str = "dark",
    status_code: int = 404,
) -> Response:
    svg = render_error_svg(
        message,
        platform=platform,
        username=username,
        accent=accent,
        theme=theme,
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        status_code=status_code,
        headers={
            "Cache-Control": "public, max-age=300",
            "Content-Type": "image/svg+xml; charset=utf-8",
        },
    )
