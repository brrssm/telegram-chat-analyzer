"""Self-contained HTML dashboard for --all mode (no scripts, no external assets)."""
import html

from .crosschat import AllStats
from .formatting import format_duration, format_percent, readable_kind

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

CSS = """
:root{color-scheme:light dark;--bg:#f6f7fb;--card:#fff;--ink:#1c2230;--muted:#5b6578;--line:#dde2ee;--accent:#2a6df4;--accent2:#0f9d8a;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#10131a;--card:#181c26;--ink:#e8ecf5;--muted:#9aa6bd;--line:#2a3142;--accent:#6ea0ff;--accent2:#3ccfb8;--warn:#fbbf24}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Tahoma,"Noto Sans Arabic",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}h1{font-size:1.6rem;margin:.2em 0}h2{font-size:1.15rem;margin:1.8em 0 .6em}h3{font-size:1rem;margin:1.2em 0 .4em}
.muted{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.card b{display:block;font-size:1.5rem}
.note{background:var(--card);border:1px solid var(--line);border-inline-start:4px solid var(--warn);border-radius:8px;padding:10px 14px;margin:10px 0}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:12px}
th,td{padding:8px 10px;text-align:start;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
td.n,th.n{text-align:end;font-variant-numeric:tabular-nums}[dir=auto]{unicode-bidi:plaintext}
.bar{display:block;height:10px;border-radius:5px;background:var(--accent);min-width:2px}.row{display:grid;grid-template-columns:minmax(90px,200px) 1fr 70px;gap:10px;align-items:center;margin:4px 0}
.row span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row span:last-child{text-align:end;font-variant-numeric:tabular-nums}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:10px 0;padding:6px 14px}summary{cursor:pointer;font-weight:600;padding:8px 0}
svg text{fill:var(--muted);font-size:10px}svg .col{fill:var(--accent)}svg .col:hover{fill:var(--accent2)}.tag{font-size:.75rem;border:1px solid var(--line);border-radius:99px;padding:1px 8px;color:var(--muted)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px}dt{font-weight:600}dd{margin:0;color:var(--muted)}
"""


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def _num(value):
    return f"{value:,}" if isinstance(value, int) else esc(value)


def _bars(pairs, formatter=_num):
    peak = max((value for _, value in pairs), default=0)
    if not pairs or peak <= 0:
        return '<p class="muted">No data.</p>'
    rows = []
    for label, value in pairs:
        width = max(1.0, value / peak * 100)
        rows.append(
            f'<div class="row"><span dir="auto" title="{esc(label)}">{esc(label)}</span>'
            f'<span role="img" aria-label="{esc(label)}: {esc(formatter(value))}"><i class="bar" style="width:{width:.1f}%"></i></span>'
            f"<span>{esc(formatter(value))}</span></div>"
        )
    return "".join(rows)


def _columns(series, title):
    """Inline SVG column chart; hovering a column shows its label and value."""
    if not series:
        return '<p class="muted">No data.</p>'
    peak = max(count for _, count in series) or 1
    width, height, pad = 640, 140, 18
    slot = (width - pad) / len(series)
    parts = [f'<svg viewBox="0 0 {width} {height + 18}" role="img" aria-label="{esc(title)}" width="100%">']
    for i, (label, count) in enumerate(series):
        h = count / peak * height
        x = pad + i * slot
        parts.append(
            f'<rect class="col" x="{x:.1f}" y="{height - h:.1f}" width="{max(slot - 1, 1):.1f}" height="{h:.1f}">'
            f"<title>{esc(label)}: {count:,}</title></rect>"
        )
    step = max(1, len(series) // 8)
    for i in range(0, len(series), step):
        parts.append(f'<text x="{pad + i * slot:.1f}" y="{height + 13}">{esc(series[i][0])}</text>')
    parts.append(f'<text x="0" y="10">{peak:,}</text></svg>')
    return "".join(parts)


def _heatmap(grid):
    peak = max((v for row in grid for v in row), default=0)
    if peak == 0:
        return '<p class="muted">No data.</p>'
    cell, left = 22, 34
    parts = [f'<svg viewBox="0 0 {left + 24 * cell} {7 * cell + 16}" role="img" aria-label="Messages by weekday and hour" width="100%">']
    for d, row in enumerate(grid):
        parts.append(f'<text x="0" y="{d * cell + 15}">{WEEKDAYS[d]}</text>')
        for h, value in enumerate(row):
            opacity = 0.07 + 0.93 * value / peak if value else 0.04
            parts.append(
                f'<rect x="{left + h * cell}" y="{d * cell}" width="{cell - 2}" height="{cell - 2}" rx="3" '
                f'fill="var(--accent)" fill-opacity="{opacity:.2f}"><title>{WEEKDAYS[d]} {h:02d}:00 - {value:,} messages</title></rect>'
            )
    for h in range(0, 24, 3):
        parts.append(f'<text x="{left + h * cell}" y="{7 * cell + 12}">{h:02d}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _table(headers, rows, numeric=()):
    head = "".join(f'<th scope="col"{" class=n" if i in numeric else ""}>{esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(
            f'<td{" class=n" if i in numeric else ""}{" dir=auto" if i == 0 else ""}>{cell}</td>' for i, cell in enumerate(row)
        ) + "</tr>"
        for row in rows
    )
    return f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _chat_section(summary, top):
    s = summary.stats
    owner = "unknown" if summary.owner_messages is None else _num(summary.owner_messages)
    facts = [
        ("Messages", _num(summary.total_messages)),
        ("Your messages", owner),
        ("Senders", _num(summary.unique_senders)),
        ("Active days", _num(summary.active_days)),
        ("Period", f"{esc(summary.first_date)} to {esc(summary.last_date)}"),
        ("Median per active day", f"{s.median_per_active_day:g}"),
        ("Longest streak", f"{s.streak_days} days"),
        ("Longest silence", esc(format_duration(s.silence_seconds))),
        ("Busiest weekday / hour", f"{WEEKDAYS[s.most_active_weekday]} / {s.most_active_hour:02d}:00"),
    ]
    cards = "".join(f'<div class="card">{esc(k)}<b>{v}</b></div>' for k, v in facts)
    senders = ""
    if summary.unique_senders > 1:
        pairs = [(p.name, p.messages) for p in s.people[:top]]
        senders = f"<h3>Messages per sender</h3>{_bars(pairs)}"
    media = f"<h3>Media</h3>{_bars(list(s.media_totals.items()))}" if s.media_totals else ""
    words = ""
    if s.top_words:
        words = "<h3>Top words</h3><p dir=\"auto\">" + ", ".join(f"{esc(w)} ({c})" for w, c in s.top_words) + "</p>"
    return (
        f'<details><summary dir="auto">{esc(summary.name)} <span class="tag">{esc(readable_kind(summary.kind))}</span> '
        f'<span class="muted">{summary.total_messages:,} messages</span></summary>'
        f'<div class="cards">{cards}</div>'
        f"<h3>Monthly trend</h3>{_columns(s.monthly, 'Messages per month')}"
        f"<h3>Weekday / hour heatmap</h3>{_heatmap(s.heatmap)}{senders}{media}{words}</details>"
    )


def render_all_report(stats: AllStats, top: int = 10) -> str:
    cards = [
        ("Chats analyzed", _num(stats.chats_analyzed)),
        ("Total messages", _num(stats.total_messages)),
        ("Your messages", "unknown" if stats.owner_messages is None else _num(stats.owner_messages)),
        ("Date range", esc(f"{stats.range_since or 'start'} to {stats.range_until or 'end'}")),
    ]
    out = [
        '<!doctype html><html lang="en" dir="auto"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>Telegram analytics - all chats</title><style>{CSS}</style></head><body><main>",
        "<h1>Telegram analytics: all chats</h1>",
        f'<p class="muted">Generated locally by tgstats {esc(stats.tool_version)} (report schema {stats.schema_version}). '
        f'{"Names are anonymized; message text is not, so top words may still reveal content. " if stats.anonymized else ""}'
        "Raw messages are never included.</p>",
        '<section class="cards" aria-label="Summary">' + "".join(f'<div class="card">{k}<b>{v}</b></div>' for k, v in cards) + "</section>",
    ]
    for warning in stats.warnings:
        out.append(f'<div class="note" role="note">{esc(warning)}</div>')
    if not stats.chats:
        out.append('<div class="note" role="alert">No chat has messages in the selected date range, so there is nothing to chart.</div>')
    else:
        out.append("<h2>Chat ranking</h2>")
        out.append(_table(
            ["Chat", "Type", "Messages", "Your msgs", "Senders", "Active days", "Avg chars", "Media", "First", "Last"],
            [
                [esc(c.name), esc(readable_kind(c.kind)), _num(c.total_messages),
                 "unknown" if c.owner_messages is None else _num(c.owner_messages), _num(c.unique_senders),
                 _num(c.active_days), "n/a" if c.avg_message_chars is None else f"{c.avg_message_chars:.0f}",
                 _num(c.media_messages), esc(c.first_date), esc(c.last_date)]
                for c in stats.chats
            ],
            numeric=range(2, 10),
        ))
        titles = {
            "most_messages": "Most messages", "most_active_days": "Most active days",
            "most_owner_messages": "Most messages by you", "longest_average_message": "Longest average message (chars)",
            "most_media": "Most media",
        }
        out.append("<h2>Leaders</h2><div class=\"cards\" style=\"grid-template-columns:repeat(auto-fit,minmax(300px,1fr))\">")
        for key, title in titles.items():
            if key in stats.rankings:
                pairs = [(r["chat"], r["value"]) for r in stats.rankings[key]]
                out.append(f'<div class="card"><h3 style="margin-top:0">{esc(title)}</h3>{_bars(pairs)}</div>')
        out.append("</div>")
        out.append("<h2>Activity by chat type</h2>")
        out.append(_bars([(f"{r['category']} ({r['chats']})", r["messages"]) for r in stats.by_category]))
        out.append(f"<h2>Activity over time (all chats)</h2>{_columns([tuple(x) for x in stats.monthly_totals], 'Messages per month, all chats')}")
        if stats.comparison:
            cmp = stats.comparison
            out.append("<h2>Date range comparison</h2>")
            out.append(f'<p class="muted">A: {esc(cmp["range_a"]["since"] or "start")} to {esc(cmp["range_a"]["until"] or "end")} &middot; '
                       f'B: {esc(cmp["range_b"]["since"] or "start")} to {esc(cmp["range_b"]["until"] or "end")}. Total A {cmp["total_a"]:,}, B {cmp["total_b"]:,}.</p>')
            out.append(_table(["Chat", "A", "B", "Change", "Change %"], [
                [esc(r["chat"]), _num(r["range_a"]), _num(r["range_b"]), f'{r["change"]:+,}',
                 "n/a" if r["change_pct"] is None else f'{r["change_pct"]:+.0f}%'] for r in cmp["chats"]
            ], numeric=range(1, 5)))
        out.append("<h2>Per-chat details</h2>")
        out.extend(_chat_section(c, top) for c in stats.chats)
    if stats.skipped:
        out.append(f"<h2>Skipped chats</h2><p class=\"muted\">{len(stats.skipped)} chat(s) had no messages in this range.</p>")
        out.append("<ul>" + "".join(f'<li dir="auto">{esc(s["name"])} - {esc(s["reason"])}</li>' for s in stats.skipped) + "</ul>")
    out.append("<h2>Metric definitions</h2><dl>" + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in stats.definitions.items()) + "</dl>")
    out.append("</main></body></html>")
    return "".join(out)
