"""Tests for markdown to Telegram HTML formatter."""

import pytest

from src.telegram.markdown_formatter import (
    markdown_to_telegram_html,
    split_message_for_telegram,
)


class TestMarkdownToTelegramHtml:
    """Tests for markdown_to_telegram_html function."""

    def test_empty_text(self):
        """Test empty text returns empty."""
        assert markdown_to_telegram_html("") == ""
        assert markdown_to_telegram_html(None) is None

    def test_plain_text(self):
        """Test plain text without markdown passes through."""
        text = "Hello, this is plain text"
        result = markdown_to_telegram_html(text)
        assert result == "Hello, this is plain text"

    def test_bold_double_asterisk(self):
        """Test bold with double asterisks."""
        text = "This is **bold** text"
        result = markdown_to_telegram_html(text)
        assert result == "This is <b>bold</b> text"

    def test_bold_double_underscore(self):
        """Test bold with double underscores."""
        text = "This is __bold__ text"
        result = markdown_to_telegram_html(text)
        assert result == "This is <b>bold</b> text"

    def test_italic_single_asterisk(self):
        """Test italic with single asterisks."""
        text = "This is *italic* text"
        result = markdown_to_telegram_html(text)
        assert result == "This is <i>italic</i> text"

    def test_italic_single_underscore(self):
        """Test italic with single underscores."""
        text = "This is _italic_ text"
        result = markdown_to_telegram_html(text)
        assert result == "This is <i>italic</i> text"

    def test_strikethrough(self):
        """Test strikethrough conversion."""
        text = "This is ~~strikethrough~~ text"
        result = markdown_to_telegram_html(text)
        assert result == "This is <s>strikethrough</s> text"

    def test_inline_code(self):
        """Test inline code conversion."""
        text = "This is `code` inline"
        result = markdown_to_telegram_html(text)
        assert result == "This is <code>code</code> inline"

    def test_code_block(self):
        """Test code block conversion."""
        text = "```\nprint('hello')\n```"
        result = markdown_to_telegram_html(text)
        assert "<pre>" in result
        assert "print(&#x27;hello&#x27;)" in result  # HTML escaped

    def test_code_block_with_language(self):
        """Test code block with language specification."""
        text = "```python\nprint('hello')\n```"
        result = markdown_to_telegram_html(text)
        assert "<pre><code>" in result
        assert "print(&#x27;hello&#x27;)" in result

    def test_link_conversion(self):
        """Test link conversion."""
        text = "Check [this link](https://example.com)"
        result = markdown_to_telegram_html(text)
        assert result == 'Check <a href="https://example.com">this link</a>'

    def test_header_to_bold(self):
        """Test headers converted to bold."""
        text = "# Header 1\n## Header 2\n### Header 3"
        result = markdown_to_telegram_html(text)
        assert "<b>Header 1</b>" in result
        assert "<b>Header 2</b>" in result
        assert "<b>Header 3</b>" in result

    def test_unordered_list_dash(self):
        """Test unordered list with dashes."""
        text = "- Item 1\n- Item 2"
        result = markdown_to_telegram_html(text)
        assert "• Item 1" in result
        assert "• Item 2" in result

    def test_unordered_list_asterisk(self):
        """Test unordered list with asterisks."""
        text = "* Item 1\n* Item 2"
        result = markdown_to_telegram_html(text)
        assert "• Item 1" in result
        assert "• Item 2" in result

    def test_html_escaping(self):
        """Test HTML entities are escaped."""
        text = "Use <script> and & ampersand"
        result = markdown_to_telegram_html(text)
        assert "&lt;script&gt;" in result
        assert "&amp; ampersand" in result

    def test_code_preserves_content(self):
        """Test code blocks preserve markdown-like content."""
        text = "```\n**not bold** and *not italic*\n```"
        result = markdown_to_telegram_html(text)
        # Inside code block, markdown should not be processed
        assert "<b>" not in result
        assert "<i>" not in result

    def test_combined_formatting(self):
        """Test multiple formatting types together."""
        text = "**Bold** and *italic* and `code`"
        result = markdown_to_telegram_html(text)
        assert "<b>Bold</b>" in result
        assert "<i>italic</i>" in result
        assert "<code>code</code>" in result


class TestSplitMessageForTelegram:
    """Tests for split_message_for_telegram function."""

    def test_short_message(self):
        """Test short message returns single chunk."""
        text = "Short message"
        result = split_message_for_telegram(text)
        assert result == ["Short message"]

    def test_exact_limit_message(self):
        """Test message at exact limit returns single chunk."""
        text = "x" * 4096
        result = split_message_for_telegram(text)
        assert len(result) == 1

    def test_long_message_split(self):
        """Test long message is split into chunks."""
        text = "x" * 5000
        result = split_message_for_telegram(text)
        assert len(result) == 2
        assert len(result[0]) <= 4096
        assert len(result[1]) <= 4096

    def test_split_at_newline(self):
        """Test splitting prefers newline boundaries."""
        text = "A" * 3000 + "\n" + "B" * 2000
        result = split_message_for_telegram(text)
        assert len(result) == 2
        assert result[0].endswith("\n") or result[1].startswith("B")

    def test_split_at_sentence(self):
        """Test splitting prefers sentence boundaries."""
        text = "A" * 3000 + ". " + "B" * 2000
        result = split_message_for_telegram(text)
        assert len(result) == 2

    def test_custom_max_length(self):
        """Test custom max length."""
        text = "x" * 200
        result = split_message_for_telegram(text, max_length=100)
        assert len(result) == 2
        assert all(len(chunk) <= 100 for chunk in result)

    def test_preserves_all_content(self):
        """Test all content is preserved after splitting."""
        text = "Hello world! " * 500
        result = split_message_for_telegram(text)
        reassembled = "".join(result)
        assert reassembled == text
