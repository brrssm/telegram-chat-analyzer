import html
import math

from .formatting import (
    WEEKDAYS_SHORT,
    format_award_value,
    format_duration,
    format_percent,
    readable_kind,
)
from .textutils import emoji_display

CSS = """
:root{--bg:#f4f6f9;--card:#ffffff;--text:#1b2430;--muted:#667385;--accent:#2f7de1;--accent2:#7b5cf0;--green:#22a06b;--border:#e1e6ee;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0f141b;--card:#171d27;--text:#e7ebf1;--muted:#8b97a8;--accent:#5ba3ff;--accent2:#a08cff;--green:#41c28c;--border:#262f3d;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Tahoma,Roboto,sans-serif;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 64px}
h1{margin:0 0 4px;font-size:28px}
h2{margin:36px 0 12px;font-size:20px}
h3{margin:0 0 10px;font-size:15px}
.muted{color:var(--muted);font-size:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.card b{display:block;font-size:22px}
.card span{color:var(--muted);font-size:13px}
.panel{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;overflow-x:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600}
.track{height:8px;background:var(--border);border-radius:4px;overflow:hidden;min-width:70px}
.fill{height:100%;background:var(--accent);border-radius:4px}
.row{display:grid;grid-template-columns:minmax(70px,1fr) 2fr auto;gap:10px;align-items:center;margin:6px 0;font-size:14px}
.row .num{color:var(--muted);font-variant-numeric:tabular-nums}
.vchart{display:flex;align-items:flex-end;gap:3px;height:170px}
.col{flex:1;min-width:0;height:100%;display:flex;flex-direction:column}
.barbox{flex:1;display:flex;align-items:flex-end}
.vbar{width:100%;background:var(--accent);border-radius:3px 3px 0 0;min-height:1px}
.col span{height:16px;font-size:10px;color:var(--muted);text-align:center;overflow:hidden;white-space:nowrap}
.chip{display:inline-block;margin:3px 6px 3px 0;padding:3px 10px;border:1px solid var(--border);border-radius:999px;font-size:14px}
.foot{margin-top:40px;text-align:center}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def _cards(stats):
    items = [
        (f"{stats.total_messages:,}", "messages"),
        (f"{stats.span_days:,}", "days covered"),
        (f"{stats.participants:,}", "participants"),
        (f"{stats.avg_per_day:.1f}", "messages per day"),
        (f"{stats.busiest_day_count:,}", f"messages on {stats.busiest_day}"),
        (f"{stats.streak_days}", "day longest streak"),
    ]
    if stats.silence_start:
        items.append((format_duration(stats.silence_seconds), "longest silence"))
    if stats.median_reply_seconds is not None:
        items.append((format_duration(stats.median_reply_seconds), "median reply time"))
    cards = "".join(f'<div class="card"><b>{esc(value)}</b><span>{esc(label)}</span></div>' for value, label in items)
    return f'<div class="cards">{cards}</div>'


def _people(stats, top):
    shown = stats.people[:top]
    peak = max(person.messages for person in shown)
    rows = []
    for person in shown:
        width = person.messages / peak * 100
        reply = format_duration(person.median_reply_seconds) if person.median_reply_seconds is not None else "-"
        rows.append(
            "<tr>"
            f'<td dir="auto">{esc(person.name)}</td>'
            f"<td>{person.messages:,}</td>"
            f'<td><div class="track"><div class="fill" style="width:{width:.1f}%"></div></div></td>'
            f"<td>{format_percent(person.share)}</td>"
            f"<td>{person.avg_words:.1f}</td>"
            f"<td>{person.emojis:,}</td>"
            f"<td>{person.questions:,}</td>"
            f"<td>{sum(person.media.values()):,}</td>"
            f"<td>{person.conversations_started:,}</td>"
            f"<td>{esc(reply)}</td>"
            "</tr>"
        )
    head = "".join(
        f"<th>{esc(label)}</th>"
        for label in ("Person", "Messages", "", "Share", "Words/msg", "Emojis", "Questions", "Media", "Starts", "Median reply")
    )
    note = ""
    if stats.participants > len(shown):
        note = f'<p class="muted">Showing the top {len(shown)} of {stats.participants} participants.</p>'
    return f'<h2>People</h2><div class="panel"><table><tr>{head}</tr>{"".join(rows)}</table></div>{note}'


def _vbars(values, labels):
    peak = max(values) or 1
    every = max(1, math.ceil(len(values) / 12))
    columns = []
    for index, (value, label) in enumerate(zip(values, labels)):
        height = value / peak * 100
        shown = esc(label) if index % every == 0 else "&nbsp;"
        columns.append(
            f'<div class="col" title="{esc(label)}: {value:,}">'
            f'<div class="barbox"><div class="vbar" style="height:{height:.1f}%"></div></div>'
            f"<span>{shown}</span></div>"
        )
    return f'<div class="vchart">{"".join(columns)}</div>'


def _activity(stats):
    hours = _vbars(stats.hourly, [f"{hour:02d}" for hour in range(24)])
    days = _vbars(stats.weekday, list(WEEKDAYS_SHORT))
    months = _vbars([count for _, count in stats.monthly], [label for label, _ in stats.monthly])
    return (
        "<h2>Activity</h2>"
        f'<div class="panel"><h3>Messages by hour of day</h3>{hours}</div><br>'
        f'<div class="grid"><div class="panel"><h3>By weekday</h3>{days}</div>'
        f'<div class="panel"><h3>By month</h3>{months}</div></div>'
    )


def _word_rows(pairs):
    if not pairs:
        return '<p class="muted">Nothing to show.</p>'
    peak = pairs[0][1] or 1
    return "".join(
        f'<div class="row"><span dir="auto">{esc(word)}</span>'
        f'<div class="track"><div class="fill" style="width:{count / peak * 100:.1f}%"></div></div>'
        f'<span class="num">{count:,}</span></div>'
        for word, count in pairs
    )


def _words(stats):
    blocks = []
    if stats.participants > 1:
        blocks.append(("Everyone", stats.top_words))
    blocks.extend((person.name, person.top_words) for person in stats.people[:4])
    panels = "".join(f'<div class="panel"><h3 dir="auto">{esc(title)}</h3>{_word_rows(words)}</div>' for title, words in blocks)
    signatures = [person for person in stats.people[:6] if person.signature_words]
    extra = ""
    if signatures:
        rows = "".join(
            f'<tr><td dir="auto">{esc(person.name)}</td><td dir="auto" style="text-align:left">'
            f'{esc("   ".join(word for word, _ in person.signature_words))}</td></tr>'
            for person in signatures
        )
        extra = f'<br><div class="panel"><h3>Signature words (said more than by others)</h3><table>{rows}</table></div>'
    return f'<h2>Words</h2><div class="grid">{panels}</div>{extra}'


def _chips(pairs, limit):
    return "".join(f'<span class="chip">{esc(emoji_display(emoji))} {count:,}</span>' for emoji, count in pairs[:limit])


def _emojis(stats):
    if not stats.top_emojis:
        return ""
    panels = [f'<div class="panel"><h3>Everyone</h3>{_chips(stats.top_emojis, 10)}</div>']
    for person in stats.people[:4]:
        if person.top_emojis:
            panels.append(f'<div class="panel"><h3 dir="auto">{esc(person.name)}</h3>{_chips(person.top_emojis, 8)}</div>')
    media = ""
    if stats.media_totals:
        chips = "".join(
            f'<span class="chip">{esc(name.replace("_", " "))} {count:,}</span>' for name, count in stats.media_totals.items()
        )
        media = f'<br><div class="panel"><h3>Media shared</h3>{chips}</div>'
    return f'<h2>Emojis</h2><div class="grid">{"".join(panels)}</div>{media}'


def _awards(stats):
    if not stats.awards:
        return ""
    cards = "".join(
        '<div class="card">'
        f"<span>{esc(award.title)}</span>"
        f'<b dir="auto">{esc(award.winner)}</b>'
        f"<span>{esc(format_award_value(award.value, award.unit, award.is_duration))}</span></div>"
        for award in stats.awards
    )
    return f'<h2>Awards</h2><div class="cards">{cards}</div>'


def render_report(stats, top=10):
    sections = [_cards(stats), _people(stats, top), _activity(stats), _words(stats), _emojis(stats), _awards(stats)]
    subtitle = f"{stats.first_date} to {stats.last_date} · {readable_kind(stats.chat_kind)}"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(stats.chat_name)} · Chat report</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        f'<h1 dir="auto">{esc(stats.chat_name)}</h1>'
        f'<div class="muted">{esc(subtitle)}</div>'
        + "".join(sections)
        + '<p class="muted foot">Generated locally. Nothing was uploaded anywhere.</p>'
        "</div></body></html>\n"
    )
