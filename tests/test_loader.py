import json
from datetime import date, datetime

import pytest

from tgstats.errors import AppError
from tgstats.loader import (
    Chat,
    anonymize,
    detect_media,
    extract_chats,
    flatten_text,
    load_messages,
    parse_message,
    pick_chat,
    read_export,
    read_json,
)


def raw(message_id, sender, when, text="hi", **extra):
    return {"id": message_id, "type": "message", "date": when, "from": sender, "text": text, **extra}


def make_chat(name="Test", chat_id=1, messages=None):
    return Chat(name=name, kind="personal_chat", id=chat_id, raw_messages=messages or [])


def test_flatten_text_joins_rich_parts():
    value = ["a", {"type": "link", "text": "b"}, " c"]
    assert flatten_text(value) == "ab c"
    assert flatten_text(None) == ""
    assert flatten_text(5) == ""


def test_parse_message_skips_service_and_garbage():
    assert parse_message({"type": "service", "date": "2024-01-01T10:00:00"}) is None
    assert parse_message("nope") is None
    assert parse_message({"type": "message", "date": "garbage"}) is None


def test_parse_message_reads_fields():
    message = parse_message(
        raw(5, "Ali", "2024-03-01T10:00:00", "salam", reply_to_message_id=3, forwarded_from="X", edited="2024-03-01T10:05:00")
    )
    assert message.id == 5
    assert message.sender == "Ali"
    assert message.date == datetime(2024, 3, 1, 10, 0, 0)
    assert message.text == "salam"
    assert message.reply_to == 3
    assert message.forwarded
    assert message.edited


def test_parse_message_falls_back_to_unix_time_and_unknown_sender():
    message = parse_message(
        {"id": 1, "type": "message", "date": "bad", "date_unixtime": "1700000000", "from": None, "text": "x"}
    )
    assert message.date == datetime.fromtimestamp(1700000000)
    assert message.sender == "Unknown"


def test_detect_media():
    assert detect_media({"media_type": "sticker"}) == "sticker"
    assert detect_media({"photo": "x"}) == "photo"
    assert detect_media({"file": "x"}) == "file"
    assert detect_media({"text": "plain"}) is None


def test_extract_chats_single_and_full_export():
    single = {"name": "A", "type": "personal_chat", "id": 7, "messages": []}
    assert [chat.name for chat in extract_chats(single)] == ["A"]
    full = {"chats": {"list": [{"name": "A", "id": 1, "messages": []}, {"name": None, "id": 2, "messages": []}, {"name": "no messages"}]}}
    chats = extract_chats(full)
    assert [chat.name for chat in chats] == ["A", "Unnamed chat"]


def test_extract_chats_rejects_bad_structure():
    with pytest.raises(AppError):
        extract_chats([])
    with pytest.raises(AppError):
        extract_chats({"hello": "world"})


def test_pick_chat_rules():
    chats = [make_chat("Family", 1), make_chat("Work Team", 2), make_chat("Work Friends", 3)]
    assert pick_chat(chats, "1").name == "Family"
    assert pick_chat(chats, "work team").name == "Work Team"
    assert pick_chat(chats, "fam").name == "Family"
    with pytest.raises(AppError):
        pick_chat(chats)
    with pytest.raises(AppError):
        pick_chat(chats, "work")
    with pytest.raises(AppError):
        pick_chat(chats, "missing")
    assert pick_chat([chats[0]]).name == "Family"


def test_load_messages_sorts_and_filters_by_date():
    chat = make_chat(
        messages=[
            raw(2, "B", "2024-03-02T09:00:00"),
            raw(1, "A", "2024-03-01T09:00:00"),
            raw(3, "A", "2024-03-05T09:00:00"),
            {"type": "service", "date": "2024-03-01T00:00:00"},
        ]
    )
    assert [message.id for message in load_messages(chat)] == [1, 2, 3]
    assert [message.id for message in load_messages(chat, since=date(2024, 3, 2))] == [2, 3]
    assert [message.id for message in load_messages(chat, until=date(2024, 3, 2))] == [1, 2]
    with pytest.raises(AppError):
        load_messages(chat, since=date(2025, 1, 1))


def test_anonymize_ranks_by_message_count():
    chat = make_chat(
        messages=[raw(1, "Zed", "2024-03-01T09:00:00"), raw(2, "Amy", "2024-03-01T09:01:00"), raw(3, "Amy", "2024-03-01T09:02:00")]
    )
    messages = anonymize(load_messages(chat))
    assert [message.sender for message in messages] == ["Person 2", "Person 1", "Person 1"]


def test_read_json_errors(tmp_path):
    with pytest.raises(AppError):
        read_json(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(AppError):
        read_json(broken)
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00\x80")
    with pytest.raises(AppError):
        read_json(binary)


def test_read_export_accepts_folder_and_bom(tmp_path):
    data = {"name": "A", "type": "personal_chat", "id": 1, "messages": [raw(1, "A", "2024-03-01T09:00:00")]}
    (tmp_path / "result.json").write_text(json.dumps(data), encoding="utf-8-sig")
    assert read_export(tmp_path)[0].name == "A"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AppError):
        read_export(empty)
