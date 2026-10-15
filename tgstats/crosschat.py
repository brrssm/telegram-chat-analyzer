"""Analyze every chat of an export and compare them."""
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Dict, List, Optional

from . import __version__
from .loader import Chat, Message, anonymize, chat_category, select_messages
from .stats import ChatStats, DEFAULT_GAP_HOURS, analyze

SCHEMA_VERSION = 1
MIN_TEXT_FOR_AVG_LENGTH = 10

METRIC_DEFINITIONS = {
    "messages": "Parsed user/bot messages in the selected date range. Service messages (joins, pins, calls) are not counted.",
    "owner_messages": "Messages whose sender is the account owner. Only reported when the owner is known "
    "(export metadata or --me); never guessed from activity.",
    "unique_senders": "Distinct sender names seen in the chat. Channels usually have one.",
    "active_days": "Calendar days (in the exported local time) with at least one message.",
    "avg_message_chars": "Mean characters per message that has text. Media-only messages are excluded. "
    f"Ranked only for chats with at least {MIN_TEXT_FOR_AVG_LENGTH} text messages.",
    "media_messages": "Messages that carry an attachment (photo, video, voice, sticker, file, poll, ...).",
    "active_streak": "Longest run of consecutive calendar days with at least one message.",
    "longest_silence": "Longest time between two consecutive messages in the chat.",
}


@dataclass
class ChatSummary:
    name: str
    kind: str
    category: str
    id: Optional[int]
    total_messages: int
    unique_senders: int
    active_days: int
    first_date: str
    last_date: str
    avg_message_chars: Optional[float]
    text_messages: int
    media_messages: int
    forwarded: int
    edited: int
    replies: int
    owner_messages: Optional[int]
    owner_share: Optional[float]
    duplicates_dropped: int
    parts: int
    stats: ChatStats


@dataclass
class AllStats:
    schema_version: int
    tool_version: str
    range_since: Optional[str]
    range_until: Optional[str]
    anonymized: bool
    owner_known: bool
    owner_source: Optional[str]
    total_chats_in_export: int
    chats_analyzed: int
    total_messages: int
    owner_messages: Optional[int]
    chats: List[ChatSummary]
    skipped: List[dict]
    rankings: Dict[str, list]
    by_category: List[dict]
    monthly_totals: List[list]
    definitions: Dict[str, str]
    warnings: List[str] = field(default_factory=list)
    comparison: Optional[dict] = None


def _owner_matcher(owner_name, owner_id):
    """Return a predicate, or None when the owner cannot be identified."""
    if not owner_name and not owner_id:
        return None
    wanted = owner_name.casefold() if owner_name else None

    def matches(message: Message) -> bool:
        if owner_id and message.from_id:
            return message.from_id == owner_id
        return wanted is not None and message.sender.casefold() == wanted

    return matches


def _in_range(messages, since, until):
    return [
        m
        for m in messages
        if (since is None or m.date.date() >= since) and (until is None or m.date.date() <= until)
    ]


def _top(summaries, key, limit, names, minimum=None):
    rows = []
    for index, summary in enumerate(summaries):
        value = key(summary)
        if value is None or (minimum is not None and not minimum(summary)):
            continue
        rows.append((value, index))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"chat": names[index], "value": round(value, 2) if isinstance(value, float) else value}
        for value, index in rows[:limit]
        if value > 0
    ]


def analyze_all(
    chats: List[Chat],
    since: Optional[date] = None,
    until: Optional[date] = None,
    top: int = 10,
    gap_hours: float = DEFAULT_GAP_HOURS,
    owner_name: Optional[str] = None,
    owner_id: Optional[str] = None,
    owner_source: Optional[str] = None,
    anonymize_names: bool = False,
    compare_since: Optional[date] = None,
    compare_until: Optional[date] = None,
    warnings=(),
) -> AllStats:
    matcher = _owner_matcher(owner_name, owner_id)
    prepared = []
    skipped = []
    comparing = compare_since is not None or compare_until is not None
    comparison_counts = {}

    for chat in chats:
        everything = select_messages(chat)  # parsed once; ranges are filtered in memory
        messages = _in_range(everything, since, until)
        if comparing:
            comparison_counts[id(chat)] = (len(messages), len(_in_range(everything, compare_since, compare_until)))
        if not messages:
            skipped.append({"name": chat.name, "kind": chat.kind, "reason": "no messages in the selected date range"})
            continue
        owner_count = sum(1 for m in messages if matcher(m)) if matcher else None
        prepared.append((chat, messages, owner_count))

    prepared.sort(key=lambda item: (-len(item[1]), item[0].name))
    display = {}
    for index, (chat, _, _) in enumerate(prepared, start=1):
        display[id(chat)] = f"Chat {index}" if anonymize_names else chat.name
    if anonymize_names:
        skipped = [
            {"name": f"Skipped chat {i}", "kind": s["kind"], "reason": s["reason"]}
            for i, s in enumerate(skipped, start=1)
        ]

    summaries: List[ChatSummary] = []
    monthly = Counter()
    for chat, messages, owner_count in prepared:
        shown = anonymize(messages) if anonymize_names else messages
        stats = analyze(shown, display[id(chat)], chat.kind, top=top, gap_hours=gap_hours)
        for month, count in stats.monthly:
            monthly[month] += count
        summaries.append(
            ChatSummary(
                name=display[id(chat)],
                kind=chat.kind,
                category=chat_category(chat.kind),
                id=None if anonymize_names else chat.id,
                total_messages=stats.total_messages,
                unique_senders=stats.participants,
                active_days=stats.active_days,
                first_date=stats.first_date,
                last_date=stats.last_date,
                avg_message_chars=stats.avg_message_chars,
                text_messages=stats.text_messages,
                media_messages=stats.media_messages,
                forwarded=stats.forwarded_total,
                edited=stats.edited_total,
                replies=stats.replies_total,
                owner_messages=owner_count,
                owner_share=(owner_count / stats.total_messages) if owner_count is not None else None,
                duplicates_dropped=chat.duplicates,
                parts=chat.parts,
                stats=stats,
            )
        )

    names = [s.name for s in summaries]
    owner_known = matcher is not None
    owner_total = sum(s.owner_messages for s in summaries) if owner_known else None
    notes = list(warnings)
    if owner_known and summaries and owner_total == 0:
        notes.append("The account owner was not found as a sender in any selected chat; check the name given to --me.")
    if not owner_known:
        notes.append("Account owner unknown: sender-specific rankings were skipped. Pass --me \"Your Name\" to enable them.")

    rankings = {
        "most_messages": _top(summaries, lambda s: s.total_messages, top, names),
        "most_active_days": _top(summaries, lambda s: s.active_days, top, names),
        "most_media": _top(summaries, lambda s: s.media_messages, top, names),
        "longest_average_message": _top(
            summaries, lambda s: s.avg_message_chars, top, names, lambda s: s.text_messages >= MIN_TEXT_FOR_AVG_LENGTH
        ),
    }
    if owner_known:
        rankings["most_owner_messages"] = _top(summaries, lambda s: s.owner_messages, top, names)

    categories = {}
    for s in summaries:
        row = categories.setdefault(
            s.category, {"category": s.category, "chats": 0, "messages": 0, "owner_messages": 0 if owner_known else None}
        )
        row["chats"] += 1
        row["messages"] += s.total_messages
        if owner_known:
            row["owner_messages"] += s.owner_messages
    total_messages = sum(s.total_messages for s in summaries)
    by_category = sorted(categories.values(), key=lambda r: (-r["messages"], r["category"]))
    for row in by_category:
        row["share"] = row["messages"] / total_messages if total_messages else 0.0

    comparison = None
    if comparing:
        rows = []
        for chat in chats:
            a, b = comparison_counts[id(chat)]
            if a == 0 and b == 0:
                continue
            shown = display.get(id(chat), f"Chat (no messages in main range)" if anonymize_names else chat.name)
            rows.append({"chat": shown, "range_a": a, "range_b": b, "change": b - a, "change_pct": ((b - a) / a * 100) if a else None})
        rows.sort(key=lambda r: (-abs(r["change"]), r["chat"]))
        if anonymize_names:  # unmatched chats get neutral labels so no real title leaks
            seen = Counter()
            for row in rows:
                if row["chat"].startswith("Chat (no"):
                    seen["x"] += 1
                    row["chat"] = f"Other chat {seen['x']}"
        comparison = {
            "range_a": {"since": since.isoformat() if since else None, "until": until.isoformat() if until else None},
            "range_b": {"since": compare_since.isoformat() if compare_since else None, "until": compare_until.isoformat() if compare_until else None},
            "total_a": sum(r["range_a"] for r in rows),
            "total_b": sum(r["range_b"] for r in rows),
            "chats": rows[:top * 2],
        }

    return AllStats(
        schema_version=SCHEMA_VERSION,
        tool_version=__version__,
        range_since=since.isoformat() if since else None,
        range_until=until.isoformat() if until else None,
        anonymized=anonymize_names,
        owner_known=owner_known,
        owner_source=owner_source if owner_known else None,
        total_chats_in_export=len(chats),
        chats_analyzed=len(summaries),
        total_messages=total_messages,
        owner_messages=owner_total,
        chats=summaries,
        skipped=skipped,
        rankings=rankings,
        by_category=by_category,
        monthly_totals=sorted([m, c] for m, c in monthly.items()),
        definitions=dict(METRIC_DEFINITIONS),
        warnings=notes,
        comparison=comparison,
    )
