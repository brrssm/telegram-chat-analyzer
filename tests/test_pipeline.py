import json
from dataclasses import asdict

from tgstats.cli import main
from tgstats.demo import write_demo_export
from tgstats.loader import load_messages, pick_chat, read_export
from tgstats.report_html import render_report
from tgstats.stats import analyze


def demo_stats(tmp_path):
    path = tmp_path / "demo.json"
    write_demo_export(path)
    chat = pick_chat(read_export(path))
    return analyze(load_messages(chat), chat.name, chat.kind)


def test_demo_pipeline_is_consistent(tmp_path):
    stats = demo_stats(tmp_path)
    assert stats.participants == 3
    assert stats.total_messages > 1000
    assert sum(person.messages for person in stats.people) == stats.total_messages
    assert sum(stats.hourly) == stats.total_messages
    assert sum(stats.weekday) == stats.total_messages
    assert sum(count for _, count in stats.monthly) == stats.total_messages
    assert stats.awards
    assert stats.top_words
    assert stats.top_emojis


def test_demo_export_is_deterministic(tmp_path):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    write_demo_export(first)
    write_demo_export(second)
    assert first.read_bytes() == second.read_bytes()


def test_stats_are_json_serializable(tmp_path):
    stats = demo_stats(tmp_path)
    data = json.loads(json.dumps(asdict(stats), ensure_ascii=False))
    assert data["total_messages"] == stats.total_messages


def test_html_report_escapes_user_text(tmp_path):
    stats = demo_stats(tmp_path)
    stats.chat_name = "<script>alert(1)</script>"
    stats.people[0].name = '"><img src=x onerror=alert(1)>'
    report = render_report(stats)
    assert "<script" not in report
    assert "&lt;script&gt;" in report
    assert "<img" not in report
    assert "http://" not in report and "https://" not in report


def test_cli_end_to_end(tmp_path):
    export = tmp_path / "chat.json"
    report = tmp_path / "out" / "report.html"
    data = tmp_path / "out" / "stats.json"
    assert main(["demo", str(export)]) == 0
    assert main(["chats", str(export)]) == 0
    assert main(["analyze", str(export), "--html", str(report), "--json", str(data), "--anonymize", "--top", "3"]) == 0
    assert "Person 1" in report.read_text(encoding="utf-8")
    assert json.loads(data.read_text(encoding="utf-8"))["participants"] == 3
    assert main(["analyze", str(export), "--since", "2025-03-01", "--until", "2025-03-31"]) == 0


def test_cli_reports_errors_without_crashing(tmp_path):
    assert main(["analyze", str(tmp_path / "missing.json")]) == 1
    export = tmp_path / "chat.json"
    main(["demo", str(export)])
    assert main(["analyze", str(export), "--since", "2025-05-01", "--until", "2025-04-01"]) == 1
    assert main(["analyze", str(export), "--since", "2030-01-01"]) == 1
    assert main(["analyze", str(export), "--chat", "nonexistent"]) == 1
