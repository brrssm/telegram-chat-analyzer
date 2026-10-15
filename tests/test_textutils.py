from tgstats.textutils import (
    content_words,
    extract_emojis,
    extract_features,
    normalize,
    tokenize,
)


def test_normalize_converts_digits_and_arabic_letters():
    assert normalize("\u064a \u0643 \u06f1\u06f2\u06f3 \u0661\u0662\u0663") == "\u06cc \u06a9 123 123"


def test_normalize_removes_diacritics_and_lowercases():
    assert normalize("HeLLo") == "hello"
    assert normalize("بعداً") == "بعدا"


def test_tokenize_keeps_zwnj_inside_words():
    tokens = tokenize("می\u200cخوام بیام")
    assert "می\u200cخوام" in tokens
    assert "بیام" in tokens


def test_tokenize_drops_links_and_mentions():
    assert tokenize("see https://x.com/a @bob now") == ["see", "now"]


def test_tokenize_ignores_numbers_and_punctuation():
    assert tokenize("123 !!! ... سلام") == ["سلام"]


def test_content_words_filters_stopwords():
    assert content_words(tokenize("من و تو رفتیم کافه")) == ["رفتیم", "کافه"]
    assert content_words(tokenize("the cat and the hat")) == ["cat", "hat"]


def test_content_words_filters_laughter_noise():
    assert content_words(tokenize("ههههه سلام hahaha")) == ["سلام"]


def test_extract_emojis_handles_modifiers_flags_and_variation_selectors():
    found = extract_emojis("hi \U0001F602\U0001F602 \u2764\ufe0f \U0001F44D\U0001F3FD \U0001F1EE\U0001F1F7")
    assert found == [
        "\U0001F602",
        "\U0001F602",
        "\u2764",
        "\U0001F44D\U0001F3FD",
        "\U0001F1EE\U0001F1F7",
    ]


def test_extract_emojis_keeps_zwj_sequences_together():
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
    assert extract_emojis(family) == [family]


def test_extract_emojis_ignores_plain_text_and_digits():
    assert extract_emojis("123 #1 hello سلام") == []


def test_laugh_detection():
    assert extract_features("ههههه").laugh
    assert extract_features("خخخخ").laugh
    assert extract_features("hahaha").laugh
    assert extract_features("\U0001F602").laugh
    assert not extract_features("hello").laugh
    assert not extract_features("https://example.com/hahaha").laugh


def test_question_detection():
    assert extract_features("چطوری؟").question
    assert extract_features("how are you?").question
    assert not extract_features("see http://a.com/?id=1").question


def test_link_counting():
    assert extract_features("a https://x.com b www.y.org").links == 2
