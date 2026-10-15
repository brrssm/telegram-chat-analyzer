import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .textutils import content_words, extract_features

DEFAULT_GAP_HOURS = 6.0
NIGHT_END_HOUR = 5
MIN_AWARD_MESSAGES = 20
MIN_REPLY_SAMPLES = 5
SIGNATURE_MIN_COUNT = 3
SIGNATURE_TOP = 5


@dataclass
class PersonStats:
    name: str
    messages: int = 0
    text_messages: int = 0
    share: float = 0.0
    words: int = 0
    characters: int = 0
    avg_words: float = 0.0
    unique_words: int = 0
    longest_message_words: int = 0
    questions: int = 0
    links: int = 0
    forwarded: int = 0
    edited: int = 0
    replies: int = 0
    emojis: int = 0
    laughs: int = 0
    night_messages: int = 0
    night_share: float = 0.0
    conversations_started: int = 0
    reply_samples: int = 0
    median_reply_seconds: Optional[float] = None
    media: dict = field(default_factory=dict)
    hourly: list = field(default_factory=lambda: [0] * 24)
    top_words: list = field(default_factory=list)
    top_emojis: list = field(default_factory=list)
    signature_words: list = field(default_factory=list)


@dataclass
class Award:
    title: str
    winner: str
    value: float
    unit: str
    is_duration: bool


@dataclass
class ChatStats:
    chat_name: str
    chat_kind: str
    total_messages: int
    participants: int
    first_date: str
    last_date: str
    span_days: int
    active_days: int
    avg_per_day: float
    busiest_day: str
    busiest_day_count: int
    streak_days: int
    streak_start: str
    streak_end: str
    silence_seconds: float
    silence_start: Optional[str]
    silence_end: Optional[str]
    gap_hours: float
    median_reply_seconds: Optional[float]
    hourly: list
    weekday: list
    monthly: list
    media_totals: dict
    top_words: list
    top_emojis: list
    people: list
    awards: list


class _Accumulator:
    def __init__(self, name):
        self.person = PersonStats(name=name)
        self.words = Counter()
        self.emojis = Counter()
        self.vocabulary = set()
        self.replies = []


AWARD_SPECS = (
    ("Essay writer", lambda p: p.avg_words, "words per message", True, False),
    ("Night owl", lambda p: p.night_share * 100, "% of messages after midnight", True, False),
    ("Emoji lover", lambda p: p.emojis / p.messages, "emojis per message", True, False),
    ("Laugh champion", lambda p: p.laughs / p.messages * 100, "% of messages with laughter", True, False),
    ("Curious mind", lambda p: p.questions / p.messages * 100, "% of messages are questions", True, False),
    ("Conversation starter", lambda p: p.conversations_started, "conversations started", True, False),
    (
        "Fastest replier",
        lambda p: p.median_reply_seconds if p.reply_samples >= MIN_REPLY_SAMPLES else None,
        "median reply",
        False,
        True,
    ),
    ("Media sharer", lambda p: sum(p.media.values()), "media messages", True, False),
)


def month_series(first, last, counts):
    series = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        series.append((f"{year}-{month:02d}", counts.get((year, month), 0)))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return series


def longest_streak(days):
    ordered = sorted(days)
    best_length, best_start, best_end = 1, ordered[0], ordered[0]
    run_length, run_start = 1, ordered[0]
    for previous, current in zip(ordered, ordered[1:]):
        if (current - previous).days == 1:
            run_length += 1
        else:
            run_length, run_start = 1, current
        if run_length > best_length:
            best_length, best_start, best_end = run_length, run_start, current
    return best_length, best_start, best_end


def signature_words(own, overall, overall_total):
    own_total = sum(own.values())
    other_total = overall_total - own_total
    if own_total == 0 or other_total <= 0:
        return []
    scored = []
    for word, count in own.items():
        if count < SIGNATURE_MIN_COUNT:
            continue
        others = overall[word] - count
        score = ((count + 1) / (own_total + 1)) / ((others + 1) / (other_total + 1))
        if score > 1:
            scored.append((word, count, score))
    scored.sort(key=lambda item: (-item[2], -item[1], item[0]))
    return [(word, count) for word, count, _ in scored[:SIGNATURE_TOP]]


def build_awards(people):
    eligible = [person for person in people if person.messages >= MIN_AWARD_MESSAGES]
    if len(eligible) < 2:
        return []
    awards = []
    for title, getter, unit, highest, is_duration in AWARD_SPECS:
        scored = [(getter(person), person) for person in eligible]
        scored = [(value, person) for value, person in scored if value is not None]
        if len(scored) < 2:
            continue
        chooser = max if highest else min
        value, winner = chooser(scored, key=lambda item: item[0])
        if highest and value <= 0:
            continue
        awards.append(Award(title, winner.name, float(value), unit, is_duration))
    return awards


def analyze(messages, chat_name="", chat_kind="", top=10, gap_hours=DEFAULT_GAP_HOURS):
    if not messages:
        raise ValueError("no messages to analyze")
    if top < 1:
        raise ValueError("top must be at least 1")
    if gap_hours <= 0:
        raise ValueError("gap_hours must be positive")

    gap_limit = gap_hours * 3600
    accumulators = {}
    overall_media = Counter()
    hourly = [0] * 24
    weekday = [0] * 7
    day_counts = Counter()
    month_counts = Counter()
    longest_gap = 0.0
    gap_start = None
    gap_end = None
    previous = None

    for message in messages:
        accumulator = accumulators.get(message.sender)
        if accumulator is None:
            accumulator = accumulators[message.sender] = _Accumulator(message.sender)
        person = accumulator.person
        person.messages += 1

        hour = message.date.hour
        hourly[hour] += 1
        person.hourly[hour] += 1
        weekday[message.date.weekday()] += 1
        day_counts[message.date.date()] += 1
        month_counts[(message.date.year, message.date.month)] += 1

        if hour < NIGHT_END_HOUR:
            person.night_messages += 1
        if message.forwarded:
            person.forwarded += 1
        if message.edited:
            person.edited += 1
        if message.reply_to is not None:
            person.replies += 1
        if message.media:
            person.media[message.media] = person.media.get(message.media, 0) + 1
            overall_media[message.media] += 1

        if message.text.strip():
            features = extract_features(message.text)
            person.text_messages += 1
            person.words += len(features.tokens)
            person.characters += len(message.text)
            person.longest_message_words = max(person.longest_message_words, len(features.tokens))
            person.links += features.links
            person.emojis += len(features.emojis)
            person.laughs += 1 if features.laugh else 0
            person.questions += 1 if features.question else 0
            accumulator.vocabulary.update(features.tokens)
            accumulator.words.update(content_words(features.tokens))
            accumulator.emojis.update(features.emojis)

        if previous is None:
            person.conversations_started += 1
        else:
            gap = (message.date - previous.date).total_seconds()
            if gap > longest_gap:
                longest_gap = gap
                gap_start = previous.date
                gap_end = message.date
            if gap >= gap_limit:
                person.conversations_started += 1
            elif message.sender != previous.sender:
                accumulator.replies.append(gap)
        previous = message

    total = len(messages)
    ordered = sorted(accumulators.values(), key=lambda item: (-item.person.messages, item.person.name))
    overall_words = Counter()
    overall_emojis = Counter()
    all_replies = []
    for accumulator in ordered:
        overall_words.update(accumulator.words)
        overall_emojis.update(accumulator.emojis)
        all_replies.extend(accumulator.replies)
    overall_total = sum(overall_words.values())

    people = []
    for accumulator in ordered:
        person = accumulator.person
        person.share = person.messages / total
        person.avg_words = person.words / person.text_messages if person.text_messages else 0.0
        person.unique_words = len(accumulator.vocabulary)
        person.night_share = person.night_messages / person.messages
        person.reply_samples = len(accumulator.replies)
        person.median_reply_seconds = (
            float(statistics.median(accumulator.replies)) if accumulator.replies else None
        )
        person.top_words = accumulator.words.most_common(top)
        person.top_emojis = accumulator.emojis.most_common(top)
        if len(ordered) > 1:
            person.signature_words = signature_words(accumulator.words, overall_words, overall_total)
        people.append(person)

    first = messages[0].date
    last = messages[-1].date
    busiest_day, busiest_count = max(
        day_counts.items(), key=lambda item: (item[1], -item[0].toordinal())
    )
    streak_days, streak_start, streak_end = longest_streak(day_counts.keys())
    span_days = (last.date() - first.date()).days + 1

    return ChatStats(
        chat_name=chat_name,
        chat_kind=chat_kind,
        total_messages=total,
        participants=len(people),
        first_date=first.date().isoformat(),
        last_date=last.date().isoformat(),
        span_days=span_days,
        active_days=len(day_counts),
        avg_per_day=total / span_days,
        busiest_day=busiest_day.isoformat(),
        busiest_day_count=busiest_count,
        streak_days=streak_days,
        streak_start=streak_start.isoformat(),
        streak_end=streak_end.isoformat(),
        silence_seconds=longest_gap,
        silence_start=gap_start.isoformat(timespec="minutes") if gap_start else None,
        silence_end=gap_end.isoformat(timespec="minutes") if gap_end else None,
        gap_hours=gap_hours,
        median_reply_seconds=float(statistics.median(all_replies)) if all_replies else None,
        hourly=hourly,
        weekday=weekday,
        monthly=month_series(first, last, month_counts),
        media_totals=dict(overall_media.most_common()),
        top_words=overall_words.most_common(top),
        top_emojis=overall_emojis.most_common(top),
        people=people,
        awards=build_awards(people),
    )
