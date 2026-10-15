import re
from dataclasses import dataclass

ZWNJ = "\u200c"

_DIGIT_MAP = {}
for _index in range(10):
    _DIGIT_MAP[0x06F0 + _index] = str(_index)
    _DIGIT_MAP[0x0660 + _index] = str(_index)
_LETTER_MAP = {0x064A: "\u06cc", 0x0643: "\u06a9", 0x0649: "\u06cc"}
TRANSLATION = {**_DIGIT_MAP, **_LETTER_MAP}

DIACRITICS = re.compile("[\u064b-\u065f\u0670\u0640]")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+")
WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[\u200c'’])*")
NOISE_RE = re.compile(r"^(.)\1{2,}$|^(?:ha){2,}h?$")
LAUGH_RE = re.compile(r"ه{3,}|خ{3,}|(?:ha){2,}|\blol\b|\blmao\b|[\U0001F602\U0001F923]")

_EMOJI_CHAR = (
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u2B1B\u2B1C"
    r"\u2934\u2935\u231A\u231B\u23E9-\u23FA\u3030\u303D\u3297\u3299]"
)
_EMOJI_TAIL = r"[\uFE0F\U0001F3FB-\U0001F3FF]*"
EMOJI_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF]{2}"
    r"|" + _EMOJI_CHAR + _EMOJI_TAIL + r"(?:\u200d" + _EMOJI_CHAR + _EMOJI_TAIL + r")*"
)

PERSIAN_RAW = """
و در به از که این را با است برای آن یک هم نه من تو ما شما او اون ایشون
اینا اونا این~ها آن~ها اینها آنها هست هستم هستی هستید هستیم هستند
نیست نیستم نیستی نیستید نیستیم نیستند
بود بودم بودی بودیم بودید بودند باشه باشد باشم باشی باشیم باشید باشند بشه بشود بشم بشی بشن
شد شده شدم شدی شدیم شدید شدند می~شه می~شود می~شن می~شم می~شی
می~کنم می~کنی می~کنه می~کند می~کنیم می~کنید می~کنن می~کنند
کرد کردم کردی کردیم کردید کردند کرده کنم کنی کنه کند کنیم کنید کنن کنند کن
داره دارد دارم داری داریم دارید دارند دارن داشت داشتم داشتی داشته داشتیم داشتند
تا هر همه همین همون همان چه چی چرا چطور چطوری کی کجا کدوم کدام چند
اگه اگر ولی اما یا پس چون چونکه وقتی همچنین هنوز دیگه دیگر فقط خیلی خب
باید بعد قبل بین روی زیر توی برای واسه براش برام برات بهش بهم بهت بهشون
ازش ازم ازت مثل مثلا یعنی البته حتما شاید آره اره نخیر بله آخه اینجا اونجا
اینم اونم منم یه می نمی ها های ای تر ترین بی بدون مگه مگر نیز هیچ هیچی همیشه الان حالا
رو می~خوام می~خواد می~خوای می~خوایم می~خوان می~تونم می~تونی می~تونه
میشه میشود میکنم میکنی میکنه میکنیم میکنن میخوام میخواد میخوای میخوایم میخوان
میتونم میتونی میتونه بگم بگو بگی میگم میگه میگی میگن گفت گفتم
"""

ENGLISH_RAW = """
the a an and or but if so to of in on at for with from by is are was were be been am
i you he she it we they me my your his her its our their this that these those
do does did have has had not no yes ok okay oh just like get got can will would should could
there here what when where who why how all too very really also then than as up out about into more some any one
im ive dont its thats youre cant didnt isnt
"""


def _build_stopwords(raw):
    words = set()
    for item in raw.split():
        word = item.replace("~", ZWNJ)
        words.add(word)
        words.add(word.replace(ZWNJ, ""))
    return words


STOPWORDS = frozenset(_build_stopwords(PERSIAN_RAW) | _build_stopwords(ENGLISH_RAW))


@dataclass(frozen=True)
class TextFeatures:
    tokens: list
    emojis: list
    links: int
    laugh: bool
    question: bool


def normalize(text):
    return DIACRITICS.sub("", text.translate(TRANSLATION)).lower()


def _strip_links(text):
    return MENTION_RE.sub(" ", URL_RE.sub(" ", text))


def tokenize_normalized(normalized):
    tokens = []
    for match in WORD_RE.finditer(_strip_links(normalized)):
        token = match.group().strip(ZWNJ + "'’")
        if token:
            tokens.append(token)
    return tokens


def tokenize(text):
    return tokenize_normalized(normalize(text))


_EXTRA_STOPWORDS = set()


def set_extra_stopwords(words):
    """Add user-supplied stopwords (normalized the same way as tokens)."""
    _EXTRA_STOPWORDS.clear()
    for word in words:
        word = normalize(word).strip()
        if word:
            _EXTRA_STOPWORDS.add(word)


def is_content_word(token):
    bare = token.replace(ZWNJ, "")
    return len(bare) >= 2 and token not in STOPWORDS and token not in _EXTRA_STOPWORDS and not NOISE_RE.match(bare)


def content_words(tokens):
    return [token for token in tokens if is_content_word(token)]


def extract_emojis(text):
    return [match.group().replace("\ufe0f", "") for match in EMOJI_RE.finditer(text)]


def emoji_display(key):
    if len(key) == 1 and ord(key) < 0x10000:
        return key + "\ufe0f"
    return key


def extract_features(text):
    normalized = normalize(text)
    without_links = _strip_links(normalized)
    return TextFeatures(
        tokens=tokenize_normalized(normalized),
        emojis=extract_emojis(text),
        links=len(URL_RE.findall(normalized)),
        laugh=bool(LAUGH_RE.search(without_links)),
        question=("?" in without_links or "؟" in without_links),
    )
