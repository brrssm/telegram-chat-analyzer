SPARK_CHARS = "▁▂▃▄▅▆▇█"

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAYS_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

KIND_NAMES = {
    "personal_chat": "Personal chat",
    "private_group": "Private group",
    "private_supergroup": "Private supergroup",
    "public_supergroup": "Public supergroup",
    "private_channel": "Private channel",
    "public_channel": "Public channel",
    "saved_messages": "Saved messages",
    "bot_chat": "Bot chat",
}


def format_duration(seconds):
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, remainder = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {remainder:02d}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours}h {minutes:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def format_percent(fraction, digits=1):
    return f"{fraction * 100:.{digits}f}%"


def sparkline(values):
    peak = max(values) if values else 0
    if peak <= 0:
        return "·" * len(values)
    top = len(SPARK_CHARS) - 1
    return "".join(
        "·" if value == 0 else SPARK_CHARS[round(value / peak * top)]
        for value in values
    )


def bar(value, peak, width):
    if peak <= 0 or value <= 0:
        return ""
    return "█" * max(1, round(value / peak * width))


def format_award_value(value, unit, is_duration):
    if is_duration:
        return format_duration(value)
    number = float(value)
    text = f"{int(number)}" if number.is_integer() else f"{number:.1f}"
    return f"{text} {unit}"


def readable_kind(kind):
    if kind in KIND_NAMES:
        return KIND_NAMES[kind]
    return kind.replace("_", " ").capitalize() if kind else "Unknown"


def plural(count, word):
    return f"{count:,} {word}" if count == 1 else f"{count:,} {word}s"
