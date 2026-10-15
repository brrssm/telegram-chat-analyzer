from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .formatting import (
    WEEKDAYS_SHORT,
    bar,
    format_award_value,
    format_duration,
    format_percent,
    plural,
    readable_kind,
    sparkline,
)
from .loader import count_messages

console = Console()

BAR_WIDTH = 28
MONTH_LIMIT = 18


def show_banner():
    title = Text("TELEGRAM CHAT ANALYZER", style="bold cyan", justify="center")
    subtitle = Text("Everything is computed locally. Nothing leaves your computer.", style="dim", justify="center")
    console.print(Panel(Group(title, subtitle), border_style="cyan", padding=(1, 6)))


def info(message):
    console.print(Text.assemble(("i ", "bold blue"), message))


def success(message):
    console.print(Text.assemble(("✔ ", "bold green"), message))


def error(message):
    console.print(Text.assemble(("✘ Error: ", "bold red"), message))


def section(title):
    console.print()
    console.rule(Text(title, style="bold cyan"), style="cyan", align="left")


def show_overview(stats):
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    active_share = stats.active_days / stats.span_days
    rows = [
        ("Chat", stats.chat_name),
        ("Type", readable_kind(stats.chat_kind)),
        ("Period", f"{stats.first_date} to {stats.last_date} ({plural(stats.span_days, 'day')})"),
        ("Messages", f"{stats.total_messages:,} ({stats.avg_per_day:.1f} per day)"),
        ("Participants", str(stats.participants)),
        ("Active days", f"{stats.active_days:,} of {stats.span_days:,} ({format_percent(active_share, 0)})"),
        ("Busiest day", f"{stats.busiest_day} ({plural(stats.busiest_day_count, 'message')})"),
        ("Longest streak", f"{plural(stats.streak_days, 'day')} ({stats.streak_start} to {stats.streak_end})"),
    ]
    if stats.silence_start:
        rows.append(
            ("Longest silence", f"{format_duration(stats.silence_seconds)} ({stats.silence_start[:10]} to {stats.silence_end[:10]})")
        )
    if stats.median_reply_seconds is not None:
        rows.append(("Median reply time", format_duration(stats.median_reply_seconds)))
    for label, value in rows:
        table.add_row(label, Text(value))
    section("Overview")
    console.print(table)


def show_people(stats, top):
    shown = stats.people[:top]
    peak = max(person.messages for person in shown)
    table = Table(header_style="bold magenta", border_style="dim")
    table.add_column("Person", overflow="fold")
    table.add_column("Messages", justify="right")
    table.add_column("Share")
    table.add_column("Words/msg", justify="right")
    table.add_column("Emojis", justify="right")
    table.add_column("Questions", justify="right")
    table.add_column("Media", justify="right")
    table.add_column("Starts", justify="right")
    table.add_column("Median reply", justify="right")
    for person in shown:
        reply = format_duration(person.median_reply_seconds) if person.median_reply_seconds is not None else "-"
        share = f"{format_percent(person.share)} {bar(person.messages, peak, 12)}"
        table.add_row(
            Text(person.name),
            f"{person.messages:,}",
            Text(share, style="cyan"),
            f"{person.avg_words:.1f}",
            f"{person.emojis:,}",
            f"{person.questions:,}",
            f"{sum(person.media.values()):,}",
            f"{person.conversations_started:,}",
            reply,
        )
    if stats.participants > len(shown):
        table.caption = f"Showing the top {len(shown)} of {stats.participants} participants"
    section("People")
    console.print(table)
    info(f"A new conversation starts after {stats.gap_hours:g}h of silence. Reply time is the median delay when someone answers another person within that window.")


def _hour_axis():
    cells = [" "] * 24
    for hour in (0, 6, 12, 18):
        for offset, char in enumerate(str(hour)):
            cells[hour + offset] = char
    return "".join(cells)


def show_activity(stats):
    section("Activity")
    hours = stats.hourly
    peak_hour = max(range(24), key=lambda hour: (hours[hour], -hour))
    grid = Table(box=None, show_header=False, padding=(0, 2))
    grid.add_column(style="bold", no_wrap=True)
    grid.add_column(no_wrap=True)
    grid.add_row("Hours", Text(sparkline(hours), style="cyan"))
    grid.add_row("", Text(_hour_axis(), style="dim"))
    console.print(grid)
    info(f"Busiest hour: {peak_hour:02d}:00 to {peak_hour:02d}:59 with {plural(hours[peak_hour], 'message')}.")

    days = Table(title="By weekday", header_style="bold magenta", border_style="dim")
    days.add_column("Day")
    days.add_column("Messages", justify="right")
    days.add_column("")
    day_peak = max(stats.weekday)
    for name, count in zip(WEEKDAYS_SHORT, stats.weekday):
        days.add_row(name, f"{count:,}", Text(bar(count, day_peak, BAR_WIDTH), style="green"))
    console.print(days)

    months = stats.monthly[-MONTH_LIMIT:]
    table = Table(title="By month", header_style="bold magenta", border_style="dim")
    if len(stats.monthly) > MONTH_LIMIT:
        table.caption = f"Showing the last {MONTH_LIMIT} of {len(stats.monthly)} months"
    table.add_column("Month")
    table.add_column("Messages", justify="right")
    table.add_column("")
    month_peak = max(count for _, count in months)
    for label, count in months:
        table.add_row(label, f"{count:,}", Text(bar(count, month_peak, BAR_WIDTH), style="yellow"))
    console.print(table)


def _word_cell(pair):
    return Text(f"{pair[0]}  {pair[1]:,}") if pair else Text("")


def show_words(stats):
    columns = []
    if stats.participants > 1:
        columns.append(("Everyone", stats.top_words))
    columns.extend((person.name, person.top_words) for person in stats.people[:3])
    rows = max((len(words) for _, words in columns), default=0)
    section("Words")
    if rows == 0:
        info("No words to show.")
        return
    table = Table(title="Most used words", header_style="bold magenta", border_style="dim")
    table.add_column("#", justify="right", style="dim")
    for title, _ in columns:
        table.add_column(Text(title))
    for index in range(rows):
        cells = [_word_cell(words[index] if index < len(words) else None) for _, words in columns]
        table.add_row(str(index + 1), *cells)
    console.print(table)

    signatures = [person for person in stats.people[:6] if person.signature_words]
    if signatures:
        sig = Table(title="Signature words (said more than by others)", header_style="bold magenta", border_style="dim")
        sig.add_column("Person")
        sig.add_column("Words")
        for person in signatures:
            sig.add_row(Text(person.name), Text("   ".join(word for word, _ in person.signature_words)))
        console.print(sig)


def show_emojis(stats):
    section("Emojis")
    if not stats.top_emojis:
        info("No emojis found.")
        return
    table = Table(header_style="bold magenta", border_style="dim")
    table.add_column("Who")
    table.add_column("Total", justify="right")
    table.add_column("Favorites")
    table.add_row(
        "Everyone",
        f"{sum(person.emojis for person in stats.people):,}",
        Text("  ".join(f"{emoji} {count}" for emoji, count in stats.top_emojis[:8])),
    )
    for person in stats.people[:5]:
        if person.top_emojis:
            table.add_row(
                Text(person.name),
                f"{person.emojis:,}",
                Text("  ".join(f"{emoji} {count}" for emoji, count in person.top_emojis[:6])),
            )
    console.print(table)
    if stats.media_totals:
        info("Media: " + ", ".join(f"{name.replace('_', ' ')} {count:,}" for name, count in stats.media_totals.items()))


def show_awards(stats):
    if not stats.awards:
        return
    section("Awards")
    table = Table(header_style="bold magenta", border_style="dim")
    table.add_column("Award", style="bold")
    table.add_column("Winner")
    table.add_column("Value")
    for award in stats.awards:
        table.add_row(award.title, Text(award.winner, style="green"), format_award_value(award.value, award.unit, award.is_duration))
    console.print(table)


def render_all(stats, top):
    show_overview(stats)
    show_people(stats, top)
    show_activity(stats)
    show_words(stats)
    show_emojis(stats)
    show_awards(stats)
    console.print()


def show_chats(chats):
    table = Table(title="Chats in this export", header_style="bold magenta", border_style="dim")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", overflow="fold")
    table.add_column("Type")
    table.add_column("Id")
    table.add_column("Messages", justify="right")
    for index, chat in enumerate(chats, start=1):
        table.add_row(
            str(index),
            Text(chat.name),
            readable_kind(chat.kind),
            str(chat.id),
            f"{count_messages(chat):,}",
        )
    console.print(table)


def show_all_summary(stats, top):
    section("All chats")
    console.print(Text(f"{stats.chats_analyzed} chats analyzed, {stats.total_messages:,} messages"
                       + (f", {stats.owner_messages:,} by you" if stats.owner_messages is not None else ", sender unknown (use --me)")))
    for warning in stats.warnings:
        console.print(Text(f"Note: {warning}", style="yellow"))
    table = Table(title="Chat ranking", header_style="bold magenta", border_style="dim")
    for column, right in (("Chat", False), ("Type", False), ("Messages", True), ("Yours", True), ("Active days", True), ("Media", True)):
        table.add_column(column, justify="right" if right else "left", overflow="fold")
    for chat in stats.chats[:top]:
        table.add_row(
            Text(chat.name), readable_kind(chat.kind), f"{chat.total_messages:,}",
            "?" if chat.owner_messages is None else f"{chat.owner_messages:,}",
            f"{chat.active_days:,}", f"{chat.media_messages:,}",
        )
    console.print(table)
    if stats.skipped:
        console.print(Text(f"{len(stats.skipped)} chat(s) skipped: no messages in the date range.", style="dim"))
