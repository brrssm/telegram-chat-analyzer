import calendar
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

PLACEHOLDER = "(File not included. Change data exporting settings to download.)"
CHAT_NAME = "Friends Group (demo)"
LAUGHS = ("ههههه", "هههه", "خخخخ", "haha", "lol")
HOUR_WEIGHTS = (3, 2, 1, 1, 0.5, 0.5, 1, 2, 3, 4, 5, 6, 8, 8, 6, 5, 5, 6, 8, 10, 12, 12, 9, 5)
DAYS = 273
ACTIVE_DAY_RATE = 0.82


def _fix(phrases):
    return tuple(phrase.replace("~", "\u200c") for phrase in phrases)


@dataclass(frozen=True)
class Persona:
    name: str
    user_id: str
    phrases: tuple
    emojis: tuple
    emoji_rate: float
    laugh_rate: float
    media: tuple
    speak_weight: float
    start_weight: float
    reply_range: tuple


SARA = Persona(
    name="Sara",
    user_id="user1001",
    phrases=_fix(
        (
            "امروز کلاس خیلی طولانی بود ولی استاد جالب درس می~داد",
            "یادت نره فردا قبل از ظهر کتاب~ها رو برگردونی کتابخونه",
            "فیلمی که دیشب دیدم واقعاً عالی بود حتماً ببینش",
            "برنامه آخر هفته چیه؟ من فکر کنم بریم کوه",
            "دستور پخت کیک رو فرستادم برات امتحانش کن",
            "تازه از سر کار رسیدم خونه خیلی خسته~ام",
            "قهوه~ی اون کافه جدید فوق~العاده~ست باید یه روز بریم",
            "برای امتحان هفته بعد باید خیلی بیشتر درس بخونم",
            "عکس~های سفر شمال رو دیدی؟ خیلی قشنگ شدن",
            "فردا صبح زود بیدار می~شم برای دویدن توی پارک",
        )
    ),
    emojis=("❤️", "😍", "🙏", "🎉", "☕"),
    emoji_rate=0.5,
    laugh_rate=0.05,
    media=(("sticker", 0.03),),
    speak_weight=0.38,
    start_weight=0.4,
    reply_range=(30, 400),
)

ALI = Persona(
    name="Ali",
    user_id="user1002",
    phrases=_fix(
        (
            "بریم؟",
            "باشه",
            "نه بابا",
            "حالا بعداً میگم",
            "عالیه",
            "خوابم میاد",
            "کی میای؟",
            "خیلی خنده~داره",
            "ok",
            "کارم تموم شد",
            "بازی دیشب رو دیدی؟",
            "پیتزا بگیریم؟",
            "فردا کافه؟",
            "من هستم",
            "بعداً حرف می~زنیم",
        )
    ),
    emojis=("😂", "👍", "🔥"),
    emoji_rate=0.15,
    laugh_rate=0.3,
    media=(("sticker", 0.05), ("animation", 0.02)),
    speak_weight=0.34,
    start_weight=0.25,
    reply_range=(10, 150),
)

NIMA = Persona(
    name="Nima",
    user_id="user1003",
    phrases=_fix(
        (
            "ساعت چند همدیگه رو ببینیم؟",
            "کسی ماشین داره؟",
            "عکس~های سفر رو فرستادم",
            "این کتاب رو خوندی؟",
            "فردا جلسه داریم یادتون نره",
            "چه خبر؟ برنامه امشب چیه؟",
            "هوا امروز خیلی خوبه بیاید بریم کوه",
            "کافه~ی جدید کجاست؟ آدرس بده",
            "فیلم امشب رو کی می~بینه؟",
            "پروژه دانشگاه رو تموم کردین؟",
        )
    ),
    emojis=("😅", "🙏", "👍", "🍕"),
    emoji_rate=0.2,
    laugh_rate=0.08,
    media=(("photo", 0.06), ("voice_message", 0.04)),
    speak_weight=0.28,
    start_weight=0.35,
    reply_range=(5, 60),
)

PERSONAS = (SARA, ALI, NIMA)


def _unix(moment):
    return str(calendar.timegm(moment.timetuple()))


def _speaker_weights(hour):
    if hour < 5:
        return [0.2, 0.6, 0.2]
    return [persona.speak_weight for persona in PERSONAS]


def _build_timeline(rng):
    start = datetime(2025, 1, 1)
    entries = []
    for day_index in range(DAYS):
        if rng.random() > ACTIVE_DAY_RATE:
            continue
        day = start + timedelta(days=day_index)
        for _ in range(rng.choices([1, 2, 3], weights=[4, 4, 2])[0]):
            hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
            moment = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
            weights = _speaker_weights(hour)
            opening = weights if hour < 5 else [persona.start_weight for persona in PERSONAS]
            previous = None
            for _ in range(rng.randint(3, 16)):
                if previous is None:
                    speaker = rng.choices(PERSONAS, weights=opening)[0]
                else:
                    if rng.random() < 0.85:
                        pool = [persona for persona in PERSONAS if persona is not previous]
                    else:
                        pool = [previous]
                    speaker = rng.choices(
                        pool, weights=[weights[PERSONAS.index(persona)] for persona in pool]
                    )[0]
                    if speaker is previous:
                        seconds = rng.randint(3, 30)
                    else:
                        seconds = rng.randint(*speaker.reply_range)
                    if rng.random() < 0.06:
                        seconds += rng.randint(900, 2400)
                    moment += timedelta(seconds=seconds)
                entries.append((moment, speaker))
                previous = speaker
    entries.sort(key=lambda item: item[0])
    return entries


def _compose(rng, persona):
    text = rng.choice(persona.phrases)
    if rng.random() < persona.laugh_rate:
        text += " " + rng.choice(LAUGHS)
    if rng.random() < persona.emoji_rate:
        text += " " + rng.choice(persona.emojis)
    return text


def _media_fields(rng, media_type):
    if media_type == "photo":
        return {"photo": PLACEHOLDER, "width": 1280, "height": 960}
    if media_type == "sticker":
        return {"file": PLACEHOLDER, "media_type": "sticker", "sticker_emoji": rng.choice(["😂", "❤️", "👍"])}
    if media_type == "voice_message":
        return {"file": PLACEHOLDER, "media_type": "voice_message", "duration_seconds": rng.randint(3, 60)}
    return {"file": PLACEHOLDER, "media_type": media_type}


def _make_message(rng, message_id, moment, persona, recent):
    base = {
        "id": message_id,
        "type": "message",
        "date": moment.isoformat(timespec="seconds"),
        "date_unixtime": _unix(moment),
        "from": persona.name,
        "from_id": persona.user_id,
    }
    roll = rng.random()
    cumulative = 0.0
    for media_type, rate in persona.media:
        cumulative += rate
        if roll < cumulative:
            return {**base, **_media_fields(rng, media_type), "text": "", "text_entities": []}
    text = _compose(rng, persona)
    message = {**base, "text": text, "text_entities": [{"type": "plain", "text": text}]}
    if recent and rng.random() < 0.1:
        message["reply_to_message_id"] = rng.choice(recent)
    if rng.random() < 0.02:
        message["forwarded_from"] = "News Channel"
    if rng.random() < 0.01:
        edited = moment + timedelta(minutes=2)
        message["edited"] = edited.isoformat(timespec="seconds")
        message["edited_unixtime"] = _unix(edited)
    return message


def build_demo_export(seed=42):
    rng = random.Random(seed)
    timeline = _build_timeline(rng)
    opening = datetime(2025, 1, 1)
    messages = [
        {
            "id": 1,
            "type": "service",
            "date": opening.isoformat(timespec="seconds"),
            "date_unixtime": _unix(opening),
            "actor": SARA.name,
            "actor_id": SARA.user_id,
            "action": "create_group",
            "title": CHAT_NAME,
            "members": [ALI.name, NIMA.name],
            "text": "",
            "text_entities": [],
        }
    ]
    recent = []
    for index, (moment, persona) in enumerate(timeline, start=2):
        message = _make_message(rng, index, moment, persona, recent)
        messages.append(message)
        recent.append(index)
        if len(recent) > 10:
            recent.pop(0)
    return {"name": CHAT_NAME, "type": "private_group", "id": 1234567890, "messages": messages}


def write_demo_export(path):
    export = build_demo_export()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(export, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(export["messages"]) - 1
