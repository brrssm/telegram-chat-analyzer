import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.text import Text

from . import __version__, ui
from .demo import write_demo_export
from .errors import AppError
from .loader import anonymize, load_messages, pick_chat, read_export
from .report_html import render_report
from .stats import DEFAULT_GAP_HOURS, analyze


def date_arg(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a date, use YYYY-MM-DD")


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number")
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_float(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number")
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tgstats",
        description="Analyze a Telegram chat export (JSON) right on your computer.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze_cmd = commands.add_parser("analyze", help="analyze a chat export")
    analyze_cmd.add_argument("path", help="result.json, or the export folder that contains it")
    analyze_cmd.add_argument("--chat", help="chat name or id (needed for full-account exports)")
    analyze_cmd.add_argument("--since", type=date_arg, help="only messages from this date (YYYY-MM-DD)")
    analyze_cmd.add_argument("--until", type=date_arg, help="only messages up to this date (YYYY-MM-DD)")
    analyze_cmd.add_argument("--top", type=positive_int, default=10, help="how many people and words to show (default 10)")
    analyze_cmd.add_argument(
        "--gap-hours",
        type=positive_float,
        default=DEFAULT_GAP_HOURS,
        help=f"silence that starts a new conversation (default {DEFAULT_GAP_HOURS:g})",
    )
    analyze_cmd.add_argument("--anonymize", action="store_true", help="replace names with Person 1, Person 2...")
    analyze_cmd.add_argument("--html", metavar="FILE", help="also save a shareable HTML report")
    analyze_cmd.add_argument("--json", metavar="FILE", help="also save all numbers as JSON")

    chats_cmd = commands.add_parser("chats", help="list the chats inside an export")
    chats_cmd.add_argument("path", help="result.json, or the export folder that contains it")

    demo_cmd = commands.add_parser("demo", help="create a fake chat export to try the tool")
    demo_cmd.add_argument("path", nargs="?", default="demo_chat.json", help="where to save it")

    return parser


def write_output(path_text, content):
    path = Path(path_text).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as error:
        raise AppError(f"Could not write '{path}': {error.strerror or error}")
    return path


def run_analyze(args):
    if args.since and args.until and args.since > args.until:
        raise AppError("--since must not be later than --until.")
    ui.show_banner()
    with ui.console.status("Reading and analyzing..."):
        chats = read_export(Path(args.path).expanduser())
        chat = pick_chat(chats, args.chat)
        messages = load_messages(chat, args.since, args.until)
        name = chat.name
        if args.anonymize:
            messages = anonymize(messages)
            name = "Anonymous chat"
        stats = analyze(messages, name, chat.kind, top=args.top, gap_hours=args.gap_hours)
    ui.render_all(stats, args.top)
    if args.json:
        path = write_output(args.json, json.dumps(asdict(stats), ensure_ascii=False, indent=2))
        ui.success(f"JSON saved to {path}")
    if args.html:
        path = write_output(args.html, render_report(stats, args.top))
        ui.success(f"HTML report saved to {path}")
    return 0


def run_chats(args):
    ui.show_banner()
    chats = read_export(Path(args.path).expanduser())
    ui.show_chats(chats)
    return 0


def run_demo(args):
    ui.show_banner()
    count = write_demo_export(Path(args.path).expanduser())
    ui.success(f"Created a fake chat with {count:,} messages: {args.path}")
    ui.console.print()
    ui.console.print("Try it:")
    ui.console.print(Text(f"  python -m tgstats analyze {args.path}", style="cyan"))
    ui.console.print(Text(f"  python -m tgstats analyze {args.path} --html report.html", style="cyan"))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    handlers = {"analyze": run_analyze, "chats": run_chats, "demo": run_demo}
    try:
        return handlers[args.command](args)
    except AppError as error:
        ui.error(str(error))
        return 1
    except KeyboardInterrupt:
        ui.info("Interrupted.")
        return 130
