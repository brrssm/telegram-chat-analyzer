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

A full-account export (Settings, Advanced, Export Telegram data) works too. Pick a chat with `--chat`, or analyze everything with `--all`.

**Split exports.** Large exports can be spread over several files. Point the tool at the export **folder** and it finds them itself:

```
TelegramExport/
  result.json                 (may contain only metadata)
  chats/
    chat_01/messages.json, messages2.json, messages3.json, ...
    chat_02/messages.json
```

Parts of one chat are merged (numeric order, so `messages10.json` comes after `messages2.json`), duplicate messages are dropped, and different chats are never mixed. Missing or malformed files stop the run with an error that names the file. A chat listed in `result.json` whose message files are absent is skipped with a warning.

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

Windows examples (quote paths that contain spaces):

```bat
python -m tgstats analyze "C:\Users\me\Downloads\Telegram Desktop\ChatExport_2025" --chat "Alice"
python -m tgstats analyze "C:\Users\me\Downloads\TelegramExport" --all --html report.html
python -m tgstats analyze "C:\Users\me\Downloads\TelegramExport" --all --since 2025-01-01 --until 2025-06-30 --json all.json
```

Analyze **all chats** and compare them (macOS/Linux shown):

```bash
python -m tgstats analyze ~/TelegramExport --all --html report.html
python -m tgstats analyze ~/TelegramExport --all --me "Your Name" --anonymize --json all.json
python -m tgstats analyze ~/TelegramExport --all --since 2025-01-01 --until 2025-03-31 \
    --compare-since 2025-04-01 --compare-until 2025-06-30
python -m tgstats analyze ~/TelegramExport --all --json - > all.json     # only JSON on stdout
```

Single chat or single file:

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
| `--all` | Analyze every chat and add a cross-chat comparison (cannot be combined with `--chat`) |
| `--me NAME` | Your display name, so your own messages can be counted. Without it, the name from the export's `personal_information` is used; if neither exists, your messages are reported as *unknown* |
| `--compare-since`, `--compare-until` | With `--all`: a second date range compared to the main one |
| `--stopwords FILE` | Extra words to ignore in word lists (one per line, `#` for comments) |
| `--since`, `--until` | Date range, format `YYYY-MM-DD` |
| `--top N` | How many people and words to show (default 10) |
| `--gap-hours H` | Silence that starts a new conversation (default 6) |
| `--anonymize` | Replace names with Person 1, Person 2... |
| `--html FILE` | Save a shareable HTML report |
| `--json FILE` | Save all numbers as JSON. Use `--json -` to print only JSON to stdout (no banner or tables) |

With `--all`, JSON has `schema_version: 1` and the keys `chats`, `rankings`, `by_category`, `monthly_totals`, `comparison`, `definitions`, `warnings`. Single-chat JSON is unchanged. Exit codes: `0` success, `1` data/usage error, `2` invalid command line.

## How it is measured

- **New conversation:** the first message after at least `--gap-hours` of silence
- **Reply time:** when the sender changes within a conversation, the delay since the previous message. The table shows the median, so one late answer does not skew it
- **Night messages:** sent between 00:00 and 04:59, in the time zone Telegram used for the export
- **Signature words:** words a person uses clearly more often than everyone else (at least 3 times)
- **Awards:** only people with at least 20 messages compete

## Cross-chat metric definitions

- **Messages:** real messages in the date range. Service entries (joins, pins, calls) are not counted
- **Your messages:** messages whose sender matches the account owner (`from_id` when available, else the display name). Never guessed from activity. A group's total is **not** your count
- **Active days:** calendar days with at least one message
- **Average message length:** characters per message that has text, ranked only for chats with 10+ text messages
- **Media:** messages with an attachment of any type
- **Chat type:** `direct`, `group`, `channel`, `bot`, `saved`, or `other`, from Telegram's chat type
- **Streak / silence:** longest run of consecutive active days / longest gap between two consecutive messages
- **Heatmap:** message counts by weekday and hour, in the time zone Telegram exported

## Privacy

- Everything runs locally. Nothing is uploaded and no network calls are made
- `--anonymize` replaces chat titles (Chat 1, 2...), sender names (Person N) and chat IDs. **It does not anonymize message text**: top words and phrases are taken from what people wrote
- HTML reports never include raw messages, only counts, names (unless anonymized) and frequent words
- Do not commit exports or reports. `.gitignore` covers common names, but check before you push

## Troubleshooting

- *"This export contains N chats"*: add `--chat NAME_OR_ID` or `--all`
- *"No Telegram data found"*: select the export folder itself, or check that you exported as **Machine-readable JSON**
- *"not valid JSON" with a file name*: that file is damaged or was cut off; re-export it
- *Your messages show as unknown*: pass `--me "Name as shown in Telegram"`
- *Odd characters in the terminal*: open the HTML report instead

## Notes

- `--anonymize` hides sender names and the chat title, not words people typed
- Some terminals do not render right-to-left text well. The HTML report always displays Persian correctly
- Timestamps are used exactly as exported, with no time zone conversion

## Project structure

```
tgstats/
├── loader.py        read exports (single file or split parts), merge, dedupe, filter, anonymize
├── textutils.py     normalization, tokens, emojis, stop words
├── stats.py         all calculations
├── ui.py            terminal output (Rich)
├── report_html.py   self-contained HTML report (single chat)
├── report_all.py    self-contained HTML dashboard (--all)
├── crosschat.py     cross-chat analytics and rankings
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
