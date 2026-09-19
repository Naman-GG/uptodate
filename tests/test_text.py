"""Greenhouse double-escapes its description field, which broke flattening
until it was handled explicitly."""
from common.text import html_to_text, truncate_for_model


def test_greenhouse_double_escaped_html():
    raw = "&lt;p&gt;Req ID: 123&lt;br&gt;Bengaluru&lt;/p&gt;&lt;ul&gt;&lt;li&gt;3+ years&lt;/li&gt;&lt;/ul&gt;"
    out = html_to_text(raw)
    assert "<" not in out and "&lt;" not in out
    assert "Req ID: 123" in out and "3+ years" in out


def test_list_items_survive_as_separate_lines():
    """Requirements live in bullet lists; collapsing them loses the boundaries
    the extractor reads."""
    out = html_to_text("<ul><li>Python</li><li>SQL</li></ul>")
    assert out.count("-") >= 2


def test_entities_are_decoded():
    assert "Python & SQL" in html_to_text("<p>Python &amp;amp; SQL</p>")


def test_empty_input():
    assert html_to_text(None) == "" and html_to_text("") == ""


def test_truncation_marks_itself():
    out = truncate_for_model("word. " * 5000, 200)
    assert "[description truncated]" in out and len(out) < 400


def test_short_text_untouched():
    assert truncate_for_model("short", 100) == "short"
