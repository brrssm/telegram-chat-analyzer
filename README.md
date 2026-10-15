# Telegram Chat Analyzer

Turn a Telegram chat export into insights: who talks the most, when, how fast people reply, favorite words and emojis, and a few fun awards. Everything runs **locally on your computer**. Your messages are never uploaded anywhere.

## Features

- **Overview:** total messages, active days, busiest day, longest streak, longest silence
- **People:** messages, share, words per message, emojis, questions, media, who starts conversations, median reply time
- **Activity:** hour of day, weekday and monthly charts right in the terminal
- **Words and emojis:** top words (with Persian support and stop-word filtering), signature words per person, favorite emojis
- **Awards:** night owl, essay writer, laugh champion, fastest replier and more
- **Reports:** a self-contained HTML report you can share, plus JSON output
- **Privacy tools:** `--anonymize` replaces names with Person 1, Person 2...
- **Filters:** date range, specific chat from a full-account export
- Works with personal chats, groups and channels, and handles Persian, Arabic digits and ZWNJ

## Export a chat from Telegram

1. Open **Telegram Desktop** and the chat you want
2. Click the three dots (top right), then **Export chat history**
3. Untick all media, set the format to **Machine-readable JSON**, and export
4. You get a folder with a `result.json` file

A full-account export (Settings, Advanced, Export Telegram data) works too. Pick a chat with `--chat`.

## Install

```bash
git clone https://github.com/brrssm/telegram-chat-analyzer.git
cd telegram-chat-analyzer
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Try it first with a generated fake chat:

```bash
python -m tgstats demo
python -m tgstats analyze demo_chat.json
python -m tgstats analyze demo_chat.json --html report.html
```

With your own export:

```bash
python -m tgstats analyze path/to/result.json
python -m tgstats analyze path/to/export_folder --html report.html --json stats.json
python -m tgstats analyze result.json --since 2025-01-01 --until 2025-06-30
python -m tgstats analyze result.json --anonymize
python -m tgstats chats full_export.json
python -m tgstats analyze full_export.json --chat "Family"
```

| Option | Meaning |
|---|---|
| `--chat NAME_OR_ID` | Choose a chat from a full-account export |
| `--since`, `--until` | Date range, format `YYYY-MM-DD` |
| `--top N` | How many people and words to show (default 10) |
| `--gap-hours H` | Silence that starts a new conversation (default 6) |
| `--anonymize` | Replace names with Person 1, Person 2... |
| `--html FILE` | Save a shareable HTML report |
| `--json FILE` | Save all numbers as JSON |

## How it is measured

- **New conversation:** the first message after at least `--gap-hours` of silence
- **Reply time:** when the sender changes within a conversation, the delay since the previous message. The table shows the median, so one late answer does not skew it
- **Night messages:** sent between 00:00 and 04:59, in the time zone Telegram used for the export
- **Signature words:** words a person uses clearly more often than everyone else (at least 3 times)
- **Awards:** only people with at least 20 messages compete

## Notes

- `--anonymize` hides sender names and the chat title, not words people typed
- Some terminals do not render right-to-left text well. The HTML report always displays Persian correctly
- Timestamps are used exactly as exported, with no time zone conversion

## Project structure

```
tgstats/
├── loader.py        read and validate exports, filter, anonymize
├── textutils.py     normalization, tokens, emojis, stop words
├── stats.py         all calculations
├── ui.py            terminal output (Rich)
├── report_html.py   self-contained HTML report
├── cli.py           commands and options
└── demo.py          fake chat generator
tests/
```

## Tests

```bash
pytest -v
```

## License

MIT
