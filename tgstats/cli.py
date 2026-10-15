import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.text import Text

from . import __version__, ui
from .demo import write_demo_export
from .errors import AppError
from .crosschat import analyze_all
from .loader import anonymize, load_messages, pick_chat, read_export, read_export_full
from .report_all import render_all_report
from .report_html import render_report
from .textutils import set_extra_stopwords
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

    analyze_cmd = commands.add_parser(
        "analyze",
        help="analyze a chat export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  tgstats analyze "C:\\Exports\\Telegram" --chat "Alice"\n'
            '  tgstats analyze "C:\\Exports\\Telegram" --all --html report.html\n'
            '  tgstats analyze result.json --all --since 2025-01-01 --until 2025-06-30 --json out.json\n'
            "  tgstats analyze export_folder --all --json -     (JSON on stdout, nothing else)"
        ),
    )
    analyze_cmd.add_argument("path", help="result.json, or the export folder (also works for exports split into messages*.json parts)")
    target = analyze_cmd.add_mutually_exclusive_group()
    target.add_argument("--chat", help="chat name or id (needed for full-account exports)")
    target.add_argument("--all", action="store_true", help="analyze every chat and compare them")
    analyze_cmd.add_argument("--me", metavar="NAME", help="your display name, to count your own messages (otherwise read from the export if available)")
    analyze_cmd.add_argument("--stopwords", metavar="FILE", help="text file with extra words to ignore (one per line)")
    analyze_cmd.add_argument("--compare-since", type=date_arg, help="--all only: start of a second date range to compare against")
    analyze_cmd.add_argument("--compare-until", type=date_arg, help="--all only: end of the second date range")
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
    analyze_cmd.add_argument("--json", metavar="FILE", help="also save all numbers as JSON (use - to print only JSON to stdout)")

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


def _load_stopwords(path_text):
    if not path_text:
        set_extra_stopwords([])
        return
    try:
        lines = Path(path_text).expanduser().read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise AppError(f"Could not read stopwords file '{path_text}': {error.strerror or error}")
    set_extra_stopwords(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def _validate(args):
    if args.since and args.until and args.since > args.until:
        raise AppError("--since must not be later than --until.")
    if args.compare_since and args.compare_until and args.compare_since > args.compare_until:
        raise AppError("--compare-since must not be later than --compare-until.")
    if (args.compare_since or args.compare_until) and not args.all:
        raise AppError("--compare-since/--compare-until only work together with --all.")
    if args.json == "-" and args.html == "-":
        raise AppError("Only one of --json and --html can print to stdout.")


def run_analyze_all(args, quiet):
    export = read_export_full(Path(args.path).expanduser())
    owner_name, owner_id, source = export.owner_name, export.owner_id, "export metadata"
    if args.me:
        owner_name, owner_id, source = args.me, None, "--me"
    elif not owner_name and not owner_id:
        source = None
    stats = analyze_all(
        export.chats,
        since=args.since,
        until=args.until,
        top=args.top,
        gap_hours=args.gap_hours,
        owner_name=owner_name,
        owner_id=owner_id,
        owner_source=source,
        anonymize_names=args.anonymize,
        compare_since=args.compare_since,
        compare_until=args.compare_until,
        warnings=export.warnings,
    )
    if not quiet:
        ui.show_all_summary(stats, args.top)
    if args.json:
        payload = json.dumps(asdict(stats), ensure_ascii=False, indent=2)
        if args.json == "-":
            sys.stdout.write(payload + "\n")
        else:
            ui.success(f"JSON saved to {write_output(args.json, payload)}")
    if args.html:
        ui.success(f"HTML report saved to {write_output(args.html, render_all_report(stats, args.top))}")
    return 0


def run_analyze(args):
    _validate(args)
    _load_stopwords(args.stopwords)
    quiet = args.json == "-"
    if not quiet:
        ui.show_banner()
    if args.all:
        return run_analyze_all(args, quiet)
    with ui.console.status("Reading and analyzing..."):
        chats = read_export(Path(args.path).expanduser())
        chat = pick_chat(chats, args.chat)
        messages = load_messages(chat, args.since, args.until)
        name = chat.name
        if args.anonymize:
            messages = anonymize(messages)
            name = "Anonymous chat"
        stats = analyze(messages, name, chat.kind, top=args.top, gap_hours=args.gap_hours)
    if not quiet:
        ui.render_all(stats, args.top)
    if args.json:
        payload = json.dumps(asdict(stats), ensure_ascii=False, indent=2)
        if quiet:
            sys.stdout.write(payload + "\n")
        else:
            ui.success(f"JSON saved to {write_output(args.json, payload)}")
    if args.html:
        path = write_output(args.html, render_report(stats, args.top))
        if not quiet:
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
        if getattr(args, "json", None) == "-":
            print(f"Error: {error}", file=sys.stderr)
        else:
            ui.error(str(error))
        return 1
    except KeyboardInterrupt:
        ui.info("Interrupted.")
        return 130
