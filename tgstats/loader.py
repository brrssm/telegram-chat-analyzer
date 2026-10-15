import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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
    from_id: Optional[str] = None


@dataclass(frozen=True)
class Chat:
    name: str
    kind: str
    id: Optional[int]
    raw_messages: list
    parts: int = 1
    duplicates: int = 0


@dataclass(frozen=True)
class Export:
    chats: List[Chat]
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    warnings: tuple = ()


PART_PATTERN = re.compile(r"^messages(\d*)\.json$", re.IGNORECASE)
CATEGORIES = {
    "personal_chat": "direct",
    "bot_chat": "bot",
    "private_group": "group",
    "private_supergroup": "group",
    "public_supergroup": "group",
    "private_channel": "channel",
    "public_channel": "channel",
    "saved_messages": "saved",
}


def chat_category(kind):
    return CATEGORIES.get(kind, "other")


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


def _owner_of(data):
    info = data.get("personal_information") if isinstance(data, dict) else None
    if not isinstance(info, dict):
        return None, None
    name = " ".join(
        str(info[key]).strip() for key in ("first_name", "last_name") if info.get(key)
    ).strip()
    user_id = info.get("user_id")
    return (name or None), (f"user{user_id}" if isinstance(user_id, int) else None)


def _part_number(path):
    match = PART_PATTERN.match(path.name)
    return int(match.group(1) or 1) if match else None


def _find_part_files(root):
    """Every messages*.json below root, grouped by folder, in a deterministic order."""
    folders = {}
    for path in sorted(root.rglob("*.json")):
        number = _part_number(path)
        if number is not None and path.is_file():
            folders.setdefault(path.parent, []).append((number, path.name, path))
    return {
        folder: [item[2] for item in sorted(items)]
        for folder, items in sorted(folders.items(), key=lambda pair: str(pair[0]))
    }


def _read_part(path):
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise AppError(
            f"'{path}' looks like a message file but has no \"messages\" list. "
            "The export may be incomplete or from an unsupported layout."
        )
    return data


def _dedupe(raw_messages):
    seen = set()
    unique = []
    dropped = 0
    for raw in raw_messages:
        if isinstance(raw, dict):
            message_id = raw.get("id")
            if isinstance(message_id, int):
                key = ("id", message_id)
            else:
                key = ("fallback", raw.get("date"), raw.get("from"), json.dumps(raw.get("text"), sort_keys=True))
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
        unique.append(raw)
    return unique, dropped


def _merge_chats(entries):
    """entries: list of (key, meta dict, raw messages, part_count, folder_name)."""
    merged = {}
    order = []
    for key, meta, messages, parts, label in entries:
        slot = merged.get(key)
        if slot is None:
            slot = merged[key] = {"meta": {}, "messages": [], "parts": 0, "label": label}
            order.append(key)
        for field_name in ("name", "type", "id"):
            if slot["meta"].get(field_name) in (None, "") and meta.get(field_name) not in (None, ""):
                slot["meta"][field_name] = meta[field_name]
        slot["messages"].extend(messages)
        slot["parts"] += parts
    chats = []
    for key in order:
        slot = merged[key]
        unique, dropped = _dedupe(slot["messages"])
        meta = slot["meta"]
        chats.append(
            Chat(
                name=str(meta.get("name") or slot["label"] or "Unnamed chat"),
                kind=str(meta.get("type") or "unknown"),
                id=meta.get("id"),
                raw_messages=unique,
                parts=slot["parts"],
                duplicates=dropped,
            )
        )
    return chats


def _read_directory(root):
    warnings = []
    owner_name = owner_id = None
    entries = []
    metadata_only = []
    result = root / "result.json"
    if result.is_file():
        data = read_json(result)
        owner_name, owner_id = _owner_of(data)
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            entries.append((("file", str(result)), data, data["messages"], 1, root.name))
        elif isinstance(data, dict) and isinstance(data.get("chats"), dict):
            for item in data["chats"].get("list") or []:
                if not isinstance(item, dict):
                    continue
                key = ("id", item["id"]) if isinstance(item.get("id"), int) else ("name", str(item.get("name")))
                if isinstance(item.get("messages"), list):
                    entries.append((key, item, item["messages"], 1, str(item.get("name") or "")))
                else:
                    metadata_only.append((key, item))
        elif isinstance(data, dict) and not any(
            _find_part_files(root)
        ):
            raise AppError(
                f"'{result}' has no chats or messages and no messages*.json files were found next to it. "
                "Re-export from Telegram Desktop as JSON with 'Chat history' enabled."
            )

    known_keys = {entry[0] for entry in entries}
    meta_by_key = {key: item for key, item in metadata_only}
    folders = _find_part_files(root)
    for folder, files in folders.items():
        loaded = [(path, _read_part(path)) for path in files]
        first_meta = next(
            (data for _, data in loaded if data.get("id") is not None or data.get("name")), {}
        )
        chat_id = first_meta.get("id")
        if isinstance(chat_id, int):
            key = ("id", chat_id)
        elif ("name", str(first_meta.get("name"))) in meta_by_key:
            key = ("name", str(first_meta.get("name")))
        else:
            key = ("folder", str(folder))
        meta = dict(meta_by_key.get(key, {}))
        meta.update({k: v for k, v in first_meta.items() if k in ("name", "type", "id") and v not in (None, "")})
        if key not in known_keys and key in meta_by_key:
            meta_by_key.pop(key, None)
        elif key in meta_by_key:
            meta_by_key.pop(key, None)
        for path, data in loaded:
            entries.append((key, meta, data["messages"], 1, folder.name))

    for key, item in meta_by_key.items():
        warnings.append(
            f"Chat '{item.get('name') or key[1]}' is listed in result.json but its message files were not found; it was skipped."
        )
    if not entries:
        raise AppError(
            f"No Telegram data found in '{root}'. Expected result.json, or messages.json files "
            "(e.g. chats/chat_01/messages.json). Check that you selected the export folder."
        )
    # entries read from a single-file result.json keep exact old behaviour (single chat)
    chats = _merge_chats(entries)
    return Export(chats=chats, owner_name=owner_name, owner_id=owner_id, warnings=tuple(warnings))


def read_export_full(path):
    """Load a Telegram export (single JSON file, or a folder possibly split into parts)."""
    if path.is_dir():
        return _read_directory(path)
    data = read_json(path)
    owner_name, owner_id = _owner_of(data)
    chats = extract_chats(data)
    unique = []
    for chat in chats:
        messages, dropped = _dedupe(chat.raw_messages)
        unique.append(Chat(chat.name, chat.kind, chat.id, messages, chat.parts, dropped))
    return Export(chats=unique, owner_name=owner_name, owner_id=owner_id)


def read_export(path):
    return read_export_full(path).chats


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
        from_id=str(raw.get("from_id")) if raw.get("from_id") else None,
    )


def select_messages(chat, since=None, until=None):
    """Parsed messages in the date range, oldest first. May be empty."""
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
    messages.sort(key=lambda item: (item.date, item.id))
    return messages


def load_messages(chat, since=None, until=None):
    messages = select_messages(chat, since, until)
    if not messages:
        raise AppError("No messages found for this chat and date range.")
    return messages


def anonymize(messages):
    counts = Counter(message.sender for message in messages)
    ranked = sorted(counts, key=lambda name: (-counts[name], name))
    aliases = {name: f"Person {index}" for index, name in enumerate(ranked, start=1)}
    return [replace(message, sender=aliases[message.sender]) for message in messages]
