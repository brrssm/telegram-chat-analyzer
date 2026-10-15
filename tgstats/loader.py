import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

from .errors import AppError


@dataclass(frozen=True)
class Message:
    id: int
    sender: str
    date: datetime
    text: str
    media: Optional[str]
    forwarded: bool
    edited: bool
    reply_to: Optional[int]


@dataclass(frozen=True)
class Chat:
    name: str
    kind: str
    id: Optional[int]
    raw_messages: list


def resolve_path(path):
    if path.is_dir():
        candidate = path / "result.json"
        if candidate.is_file():
            return candidate
        raise AppError(f"No result.json found inside '{path}'.")
    return path


def read_json(path):
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise AppError(f"File not found: {path}")
    except UnicodeDecodeError:
        raise AppError("The file is not valid UTF-8 text. Use Telegram's result.json export.")
    except OSError as error:
        raise AppError(f"Could not read '{path}': {error.strerror or error}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise AppError(
            f"The file is not valid JSON ({error.msg}, line {error.lineno}). "
            "Export the chat as Machine-readable JSON."
        )


def _make_chat(item):
    return Chat(
        name=str(item.get("name") or "Unnamed chat"),
        kind=str(item.get("type") or "unknown"),
        id=item.get("id"),
        raw_messages=item["messages"],
    )


def extract_chats(data):
    if not isinstance(data, dict):
        raise AppError("Unexpected file structure: expected a JSON object.")
    if isinstance(data.get("messages"), list):
        return [_make_chat(data)]
    section = data.get("chats")
    if isinstance(section, dict) and isinstance(section.get("list"), list):
        chats = [
            _make_chat(item)
            for item in section["list"]
            if isinstance(item, dict) and isinstance(item.get("messages"), list)
        ]
        if chats:
            return chats
    raise AppError(
        "No chat found in this file. In Telegram Desktop open a chat, choose "
        "'Export chat history' and set the format to JSON."
    )


def read_export(path):
    return extract_chats(read_json(resolve_path(path)))


def count_messages(chat):
    return sum(
        1
        for raw in chat.raw_messages
        if isinstance(raw, dict) and raw.get("type") == "message"
    )


def pick_chat(chats, selector=None):
    if selector is None:
        if len(chats) == 1:
            return chats[0]
        raise AppError(
            f"This export contains {len(chats)} chats. Pick one with --chat NAME_OR_ID "
            "(run the 'chats' command to list them)."
        )
    wanted = selector.casefold()
    matches = [chat for chat in chats if str(chat.id) == selector]
    if not matches:
        matches = [chat for chat in chats if chat.name.casefold() == wanted]
    if not matches:
        matches = [chat for chat in chats if wanted in chat.name.casefold()]
    if not matches:
        raise AppError(f"No chat matches '{selector}'.")
    if len(matches) > 1:
        names = ", ".join(f"{chat.name} (id {chat.id})" for chat in matches[:5])
        raise AppError(f"'{selector}' matches {len(matches)} chats: {names}. Use the numeric id.")
    return matches[0]


def flatten_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return ""


def parse_date(date_text, unixtime):
    if isinstance(date_text, str):
        try:
            return datetime.fromisoformat(date_text).replace(tzinfo=None)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(int(unixtime))
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def detect_media(raw):
    media_type = raw.get("media_type")
    if media_type:
        return str(media_type)
    for key, name in (
        ("photo", "photo"),
        ("poll", "poll"),
        ("location_information", "location"),
        ("contact_information", "contact"),
        ("file", "file"),
    ):
        if key in raw:
            return name
    return None


def parse_message(raw):
    if not isinstance(raw, dict) or raw.get("type") != "message":
        return None
    date = parse_date(raw.get("date"), raw.get("date_unixtime"))
    if date is None:
        return None
    message_id = raw.get("id")
    reply_to = raw.get("reply_to_message_id")
    return Message(
        id=message_id if isinstance(message_id, int) else 0,
        sender=str(raw.get("from") or "Unknown"),
        date=date,
        text=flatten_text(raw.get("text")),
        media=detect_media(raw),
        forwarded="forwarded_from" in raw,
        edited="edited" in raw or "edited_unixtime" in raw,
        reply_to=reply_to if isinstance(reply_to, int) else None,
    )


def load_messages(chat, since=None, until=None):
    messages = []
    for raw in chat.raw_messages:
        message = parse_message(raw)
        if message is None:
            continue
        day = message.date.date()
        if since is not None and day < since:
            continue
        if until is not None and day > until:
            continue
        messages.append(message)
    if not messages:
        raise AppError("No messages found for this chat and date range.")
    messages.sort(key=lambda item: (item.date, item.id))
    return messages


def anonymize(messages):
    counts = Counter(message.sender for message in messages)
    ranked = sorted(counts, key=lambda name: (-counts[name], name))
    aliases = {name: f"Person {index}" for index, name in enumerate(ranked, start=1)}
    return [replace(message, sender=aliases[message.sender]) for message in messages]
