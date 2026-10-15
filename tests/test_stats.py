from datetime import datetime

import pytest

from tgstats.loader import Message
from tgstats.stats import analyze, longest_streak


def msg(message_id, sender, when, text="", media=None):
    return Message(
        id=message_id,
        sender=sender,
        date=datetime.fromisoformat(when),
        text=text,
        media=media,
        forwarded=False,
        edited=False,
        reply_to=None,
    )


@pytest.fixture
def sample():
    return [
        msg(1, "A", "2024-03-01T10:00:00", "hello there how are you"),
        msg(2, "B", "2024-03-01T10:00:30", "fine thanks \U0001F602 and you?"),
        msg(3, "A", "2024-03-01T10:01:30", "great \u0647\u0647\u0647\u0647\u0647"),
        msg(4, "A", "2024-03-01T10:02:00", "", media="photo"),
        msg(5, "B", "2024-03-01T20:00:00", "evening"),
        msg(6, "A", "2024-03-02T00:30:00", "https://example.com night"),
        msg(7, "B", "2024-03-05T09:00:00", "bye"),
    ]


def test_overview_numbers(sample):
    stats = analyze(sample, "Chat", "personal_chat")
    assert stats.total_messages == 7
    assert stats.participants == 2
    assert stats.first_date == "2024-03-01"
    assert stats.last_date == "2024-03-05"
    assert stats.span_days == 5
    assert stats.active_days == 3
    assert stats.avg_per_day == pytest.approx(1.4)
    assert stats.busiest_day == "2024-03-01"
    assert stats.busiest_day_count == 5
    assert (stats.streak_days, stats.streak_start, stats.streak_end) == (2, "2024-03-01", "2024-03-02")
    assert stats.silence_seconds == 3 * 86400 + 8.5 * 3600
    assert stats.silence_start == "2024-03-02T00:30"
    assert stats.silence_end == "2024-03-05T09:00"


def test_people_are_ranked_and_counted(sample):
    stats = analyze(sample)
    first, second = stats.people
    assert (first.name, first.messages) == ("A", 4)
    assert (second.name, second.messages) == ("B", 3)
    assert first.share == pytest.approx(4 / 7)
    assert first.text_messages == 3
    assert first.words == 8
    assert first.media == {"photo": 1}
    assert first.links == 1
    assert first.night_messages == 1
    assert second.emojis == 1
    assert second.questions == 1
    assert second.laughs == 1
    assert first.laughs == 1


def test_conversations_and_reply_times(sample):
    stats = analyze(sample)
    first, second = stats.people
    assert first.conversations_started == 1
    assert second.conversations_started == 2
    assert second.median_reply_seconds == 30.0
    assert first.median_reply_seconds == 8130.0
    assert first.reply_samples == 2
    assert stats.median_reply_seconds == 60.0


def test_gap_hours_changes_conversation_split(sample):
    stats = analyze(sample, gap_hours=24)
    assert sum(person.conversations_started for person in stats.people) == 2


def test_time_distributions(sample):
    stats = analyze(sample)
    assert stats.hourly[10] == 4
    assert stats.hourly[20] == 1
    assert stats.hourly[0] == 1
    assert stats.hourly[9] == 1
    assert sum(stats.hourly) == 7
    assert stats.weekday[4] == 5
    assert stats.weekday[5] == 1
    assert stats.weekday[1] == 1
    assert stats.monthly == [("2024-03", 7)]


def test_monthly_series_fills_empty_months():
    stats = analyze([msg(1, "A", "2024-01-15T10:00:00", "a"), msg(2, "A", "2024-04-02T10:00:00", "b")])
    assert stats.monthly == [("2024-01", 1), ("2024-02", 0), ("2024-03", 0), ("2024-04", 1)]


def test_single_message_and_single_person():
    stats = analyze([msg(1, "Solo", "2024-03-01T10:00:00", "hi")])
    assert stats.total_messages == 1
    assert stats.span_days == 1
    assert stats.silence_start is None
    assert stats.median_reply_seconds is None
    assert stats.people[0].conversations_started == 1
    assert stats.awards == []


def test_media_only_messages_do_not_break_averages():
    stats = analyze([msg(1, "A", "2024-03-01T10:00:00", "", media="sticker")])
    assert stats.people[0].avg_words == 0.0
    assert stats.media_totals == {"sticker": 1}


def test_top_words_and_signature_words():
    messages = []
    for index in range(6):
        messages.append(msg(index * 2 + 1, "A", f"2024-03-0{index + 1}T10:00:00", "pizza pizza tonight"))
        messages.append(msg(index * 2 + 2, "B", f"2024-03-0{index + 1}T10:01:00", "coffee tonight"))
    stats = analyze(messages, top=3)
    assert dict(stats.top_words) == {"pizza": 12, "tonight": 12, "coffee": 6}
    a, b = stats.people
    assert a.signature_words[0][0] == "pizza"
    assert b.signature_words[0][0] == "coffee"
    assert all(word != "tonight" for word, _ in a.signature_words)


def test_awards_need_enough_messages():
    few = [msg(1, "A", "2024-03-01T10:00:00", "x"), msg(2, "B", "2024-03-01T10:01:00", "y")]
    assert analyze(few).awards == []
    many = []
    for index in range(30):
        many.append(msg(index * 2 + 1, "A", f"2024-03-01T10:{index:02d}:00", "a long message with many words in it"))
        many.append(msg(index * 2 + 2, "B", f"2024-03-01T10:{index:02d}:30", "ok"))
    titles = {award.title: award.winner for award in analyze(many).awards}
    assert titles["Essay writer"] == "A"


def test_longest_streak_helper():
    from datetime import date

    days = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 5), date(2024, 1, 6), date(2024, 1, 7)]
    assert longest_streak(days) == (3, date(2024, 1, 5), date(2024, 1, 7))


def test_invalid_arguments():
    with pytest.raises(ValueError):
        analyze([])
    with pytest.raises(ValueError):
        analyze([msg(1, "A", "2024-03-01T10:00:00", "x")], top=0)
    with pytest.raises(ValueError):
        analyze([msg(1, "A", "2024-03-01T10:00:00", "x")], gap_hours=0)
