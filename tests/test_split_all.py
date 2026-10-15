import json
from datetime import date, datetime

import pytest

from tests.fixtures import (OWNER, full_result_export, make_messages, msg, owner_msg, single_file_export,
                            split_export, write)
from tgstats.cli import main
from tgstats.crosschat import analyze_all
from tgstats.errors import AppError
from tgstats.loader import chat_category, load_messages, read_export, read_export_full
from tgstats.report_all import render_all_report


def by_name(chats):
    return {chat.name: chat for chat in chats}


# ---- loader -----------------------------------------------------------------
def test_single_file_still_works(tmp_path):
    chats = read_export(single_file_export(tmp_path))
    assert len(chats) == 1 and chats[0].name == "Solo"
    assert len(load_messages(chats[0])) == 10


def test_full_result_json_multiple_chats(tmp_path):
    chats = by_name(read_export(full_result_export(tmp_path)))
    assert set(chats) == {"Alice", "Team", "News"}
    assert chat_category(chats["News"].kind) == "channel"


def test_root_directory_with_result_json(tmp_path):
    full_result_export(tmp_path)
    assert len(read_export(tmp_path)) == 3


def test_split_export_merges_parts_per_chat(tmp_path):
    export = read_export_full(split_export(tmp_path))
    chats = by_name(export.chats)
    assert set(chats) == {"Alice", "Team"}
    assert len(load_messages(chats["Alice"])) == 30
    assert len(load_messages(chats["Team"])) == 12
    assert chats["Alice"].parts == 3
    assert export.owner_name == "Test Owner" and export.warnings == ()


def test_split_parts_are_sorted_chronologically(tmp_path):
    chat = by_name(read_export(split_export(tmp_path)))["Alice"]
    dates = [m.date for m in load_messages(chat)]
    assert dates == sorted(dates)


def test_duplicate_messages_across_parts_are_dropped(tmp_path):
    chat = by_name(read_export(split_export(tmp_path, with_duplicate=True)))["Alice"]
    assert len(load_messages(chat)) == 30
    assert chat.duplicates == 4


def test_chats_are_not_mixed_even_with_same_message_ids(tmp_path):
    root = tmp_path / "exp"
    same = make_messages(datetime(2025, 3, 1), 5)
    write(root / "chats" / "a" / "messages.json", {"name": "A", "type": "personal_chat", "id": 1, "messages": same})
    write(root / "chats" / "b" / "messages.json", {"name": "B", "type": "personal_chat", "id": 2, "messages": same})
    chats = by_name(read_export(root))
    assert len(chats["A"].raw_messages) == 5 and len(chats["B"].raw_messages) == 5


def test_chat_folder_alone_is_supported(tmp_path):
    folder = split_export(tmp_path) / "chats" / "chat_01"
    chats = read_export(folder)
    assert len(chats) == 1 and len(chats[0].raw_messages) == 30


def test_metadata_chat_without_files_gives_warning(tmp_path):
    root = split_export(tmp_path)
    data = json.loads((root / "result.json").read_text(encoding="utf-8"))
    data["chats"]["list"].append({"name": "Ghost", "type": "personal_chat", "id": 99})
    write(root / "result.json", data)
    export = read_export_full(root)
    assert len(export.chats) == 2
    assert any("Ghost" in w for w in export.warnings)


def test_missing_files_and_empty_folder_errors(tmp_path):
    with pytest.raises(AppError):
        read_export(tmp_path / "does_not_exist.json")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AppError):
        read_export(empty)


def test_malformed_part_names_the_file(tmp_path):
    root = split_export(tmp_path)
    (root / "chats" / "chat_01" / "messages2.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(AppError, match="messages2.json|not valid JSON"):
        read_export(root)


def test_part_without_messages_list_is_unsupported(tmp_path):
    root = split_export(tmp_path)
    write(root / "chats" / "chat_01" / "messages3.json", {"oops": True})
    with pytest.raises(AppError, match="messages3.json"):
        read_export(root)


def test_unicode_paths_and_persian_text(tmp_path):
    root = tmp_path / "صادرات تلگرام"
    write(root / "result.json", {"name": "دوست", "type": "personal_chat", "id": 7, "messages": [
        owner_msg(1, datetime(2025, 1, 1, 10), "سلام دنیا 😀"), msg(2, datetime(2025, 1, 1, 11), "علی", "سلام")]})
    chat = read_export(root)[0]
    assert chat.name == "دوست" and load_messages(chat)[0].text.startswith("سلام")


# ---- cross-chat analytics ---------------------------------------------------
def analyzed(tmp_path, **kwargs):
    export = read_export_full(full_result_export(tmp_path))
    return analyze_all(export.chats, owner_name=export.owner_name, owner_id=export.owner_id,
                       owner_source="export metadata", **kwargs)


def test_cross_chat_totals_and_rankings(tmp_path):
    stats = analyzed(tmp_path)
    assert stats.chats_analyzed == 3 and stats.total_messages == 95
    assert stats.rankings["most_messages"][0] == {"chat": "Team", "value": 60}
    assert stats.rankings["most_media"][0]["chat"] == "News"
    assert stats.rankings["most_owner_messages"][0]["chat"] == "Team"
    assert stats.owner_messages == 15 + 20 + 0
    cats = {row["category"]: row for row in stats.by_category}
    assert cats["group"]["messages"] == 60 and cats["channel"]["messages"] == 5
    assert sum(c.total_messages for c in stats.chats) == stats.total_messages


def test_owner_unknown_is_not_guessed(tmp_path):
    export = read_export_full(full_result_export(tmp_path))
    stats = analyze_all(export.chats)
    assert not stats.owner_known and stats.owner_messages is None
    assert all(c.owner_messages is None for c in stats.chats)
    assert "most_owner_messages" not in stats.rankings


def test_group_total_is_not_counted_as_owner_messages(tmp_path):
    team = [c for c in analyzed(tmp_path).chats if c.name == "Team"][0]
    assert team.total_messages == 60 and team.owner_messages == 20


def test_date_filter_and_empty_chat_in_range(tmp_path):
    stats = analyzed(tmp_path, until=date(2025, 1, 1))  # News starts on Jan 2
    assert stats.total_chats_in_export == 3 and stats.chats_analyzed == 2
    assert [s["name"] for s in stats.skipped] == ["News"]
    assert all(c.last_date == "2025-01-01" for c in stats.chats)


def test_range_with_no_messages_does_not_crash(tmp_path):
    stats = analyzed(tmp_path, since=date(2030, 1, 1))
    assert stats.chats_analyzed == 0 and len(stats.skipped) == 3 and stats.chats == []
    assert "No chat has messages" in render_all_report(stats)


def test_comparison_ranges(tmp_path):
    stats = analyzed(tmp_path, since=date(2025, 1, 1), until=date(2025, 1, 5),
                     compare_since=date(2025, 1, 6), compare_until=date(2025, 1, 31))
    assert stats.comparison["total_a"] > 0 and stats.comparison["total_b"] > 0
    assert all(r["range_a"] + r["range_b"] > 0 for r in stats.comparison["chats"])


# ---- privacy ----------------------------------------------------------------
def test_anonymized_json_and_html_hide_names(tmp_path):
    stats = analyzed(tmp_path, anonymize_names=True)
    blob = json.dumps(stats.__dict__, default=lambda o: o.__dict__, ensure_ascii=False) + render_all_report(stats)
    for secret in ("Alice", "Bob", "Carol", "Team", "News", OWNER):
        assert secret not in blob, secret
    assert "Chat 1" in blob and all(c.id is None for c in stats.chats)


def test_html_escapes_injected_names(tmp_path):
    stats = analyzed(tmp_path)
    stats.chats[0].name = "<script>alert(1)</script>"
    stats.chats[0].stats.people[0].name = '"><img src=x onerror=alert(1)>'
    stats.warnings.append("<b>bad</b>")
    page = render_all_report(stats)
    assert "<script" not in page and "<img" not in page and "<b>bad" not in page
    assert "http://" not in page and "https://" not in page


def test_html_has_no_raw_message_text(tmp_path):
    root = tmp_path / "x.json"
    write(root, {"name": "C", "type": "personal_chat", "id": 1, "messages": [
        owner_msg(i, datetime(2025, 1, 1, 8 + i), "SECRET-PHRASE-ZZ") for i in range(1, 5)]})
    export = read_export_full(root)
    page = render_all_report(analyze_all(export.chats))
    assert "SECRET-PHRASE-ZZ" not in page


# ---- CLI --------------------------------------------------------------------
def test_cli_all_html_json(tmp_path, capsys):
    full_result_export(tmp_path)
    out_json, out_html = tmp_path / "o" / "a.json", tmp_path / "o" / "a.html"
    assert main(["analyze", str(tmp_path / "result.json"), "--all", "--json", str(out_json), "--html", str(out_html)]) == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1 and data["chats_analyzed"] == 3
    assert "Chat ranking" in out_html.read_text(encoding="utf-8")


def test_cli_all_on_split_root_directory(tmp_path, capsys):
    root = split_export(tmp_path)
    assert main(["analyze", str(root), "--all", "--json", "-"]) == 0
    data = json.loads(capsys.readouterr().out)  # stdout is pure JSON
    assert data["total_messages"] == 42


def test_cli_all_and_chat_are_mutually_exclusive(tmp_path):
    full_result_export(tmp_path)
    with pytest.raises(SystemExit) as info:
        main(["analyze", str(tmp_path / "result.json"), "--all", "--chat", "Alice"])
    assert info.value.code == 2


def test_cli_multi_chat_without_selection_is_helpful_error(tmp_path):
    full_result_export(tmp_path)
    assert main(["analyze", str(tmp_path / "result.json")]) == 1


def test_cli_chat_mode_on_split_export(tmp_path):
    root = split_export(tmp_path)
    assert main(["analyze", str(root), "--chat", "Alice", "--html", str(tmp_path / "r.html")]) == 0


def test_cli_anonymized_all_outputs(tmp_path):
    full_result_export(tmp_path)
    j, h = tmp_path / "a.json", tmp_path / "a.html"
    assert main(["analyze", str(tmp_path / "result.json"), "--all", "--anonymize", "--json", str(j), "--html", str(h)]) == 0
    text = j.read_text(encoding="utf-8") + h.read_text(encoding="utf-8")
    assert "Alice" not in text and "Carol" not in text and OWNER not in text


def test_cli_bad_date_combo(tmp_path):
    full_result_export(tmp_path)
    assert main(["analyze", str(tmp_path / "result.json"), "--all", "--since", "2025-05-01", "--until", "2025-01-01"]) == 1
    assert main(["analyze", str(tmp_path / "result.json"), "--all", "--compare-since", "2025-01-01", "--compare-until", "2024-01-01"]) == 1
