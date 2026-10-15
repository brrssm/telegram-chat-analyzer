"""Synthetic Telegram export builders. Nothing here comes from a real conversation."""
import json
from datetime import datetime, timedelta

OWNER_ID = 1000
OWNER = "Test Owner"


def msg(message_id, when, sender, text="hello", from_id=None, **extra):
    data = {
        "id": message_id,
        "type": "message",
        "date": when.isoformat(timespec="seconds"),
        "date_unixtime": str(int(when.timestamp())),
        "from": sender,
        "from_id": from_id or f"user{abs(hash(sender)) % 9000 + 2000}",
        "text": text,
    }
    data.update(extra)
    return data


def owner_msg(message_id, when, text="hi"):
    return msg(message_id, when, OWNER, text, from_id=f"user{OWNER_ID}")


def make_messages(start, count, step_hours=7, first_id=1, senders=(OWNER, "Alice")):
    out = []
    for i in range(count):
        who = senders[i % len(senders)]
        when = start + timedelta(hours=step_hours * i)
        out.append(owner_msg(first_id + i, when, f"msg {i}") if who == OWNER else msg(first_id + i, when, who, f"msg {i}"))
    return out


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def single_file_export(tmp_path):
    return write(tmp_path / "single.json", {
        "name": "Solo", "type": "personal_chat", "id": 5,
        "messages": make_messages(datetime(2025, 1, 1, 9), 10),
    })


def full_result_export(tmp_path, name="result.json"):
    start = datetime(2025, 1, 1, 9)
    return write(tmp_path / name, {
        "personal_information": {"user_id": OWNER_ID, "first_name": "Test", "last_name": "Owner"},
        "chats": {"list": [
            {"name": "Alice", "type": "personal_chat", "id": 11, "messages": make_messages(start, 30)},
            {"name": "Team", "type": "private_supergroup", "id": 12,
             "messages": make_messages(start, 60, 5, senders=(OWNER, "Bob", "Carol"))},
            {"name": "News", "type": "public_channel", "id": 13,
             "messages": [msg(i, start + timedelta(days=i), "News", "update", photo="p.jpg") for i in range(1, 6)]},
        ]},
    })


def split_export(tmp_path, with_duplicate=False):
    """result.json holds only metadata; messages live in chats/<folder>/messages[N].json."""
    root = tmp_path / "TelegramExport"
    start = datetime(2025, 2, 1, 8)
    write(root / "result.json", {
        "personal_information": {"user_id": OWNER_ID, "first_name": "Test", "last_name": "Owner"},
        "chats": {"list": [
            {"name": "Alice", "type": "personal_chat", "id": 21},
            {"name": "Team", "type": "private_supergroup", "id": 22},
        ]},
    })
    alice = make_messages(start, 30)
    write(root / "chats" / "chat_01" / "messages.json", {"name": "Alice", "type": "personal_chat", "id": 21, "messages": alice[:10]})
    write(root / "chats" / "chat_01" / "messages2.json", {"name": "Alice", "type": "personal_chat", "id": 21,
          "messages": alice[10:20] + (alice[8:12] if with_duplicate else [])})
    write(root / "chats" / "chat_01" / "messages10.json", {"messages": alice[20:]})  # numeric, not lexical, order
    team = make_messages(start, 12, 3, first_id=500, senders=(OWNER, "Bob"))
    write(root / "chats" / "chat_02" / "messages.json", {"name": "Team", "type": "private_supergroup", "id": 22, "messages": team})
    write(root / "chats" / "chat_02" / "messages2.json", {"name": "Team", "type": "private_supergroup", "id": 22, "messages": []})
    return root
