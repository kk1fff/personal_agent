"""Convert standard markdown to Telegram-compatible HTML format."""

import html
import re
from typing import List, Tuple

# Use unique placeholders that won't be matched by markdown patterns
_CODE_BLOCK_PLACEHOLDER = "\x00CB\x00"
_INLINE_CODE_PLACEHOLDER = "\x00IC\x00"


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert standard markdown to Telegram-compatible HTML.

    Telegram supports a limited subset of HTML tags:
    - <b>bold</b>
    - <i>italic</i>
    - <u>underline</u>
    - <s>strikethrough</s>
    - <code>inline code</code>
    - <pre>code block</pre>
    - <a href="url">link</a>

    Args:
        text: Standard markdown text

    Returns:
        Telegram-compatible HTML formatted text
    """
    if not text:
        return text

    # First, extract and preserve code blocks to avoid processing markdown inside them
    code_blocks: List[Tuple[str, str]] = []
    inline_codes: List[Tuple[str, str]] = []

    # Extract fenced code blocks (```...```)
    def preserve_code_block(match: re.Match) -> str:
        placeholder = f"{_CODE_BLOCK_PLACEHOLDER}{len(code_blocks)}{_CODE_BLOCK_PLACEHOLDER}"
        language = match.group(1) or ""
        code = match.group(2)
        # Escape HTML entities in code
        escaped_code = html.escape(code)
        if language:
            code_blocks.append((placeholder, f"<pre><code>{escaped_code}</code></pre>"))
        else:
            code_blocks.append((placeholder, f"<pre>{escaped_code}</pre>"))
        return placeholder

    text = re.sub(r"```(\w*)\n?(.*?)```", preserve_code_block, text, flags=re.DOTALL)

    # Extract inline code (`...`)
    def preserve_inline_code(match: re.Match) -> str:
        placeholder = f"{_INLINE_CODE_PLACEHOLDER}{len(inline_codes)}{_INLINE_CODE_PLACEHOLDER}"
        code = match.group(1)
        escaped_code = html.escape(code)
        inline_codes.append((placeholder, f"<code>{escaped_code}</code>"))
        return placeholder

    text = re.sub(r"`([^`]+)`", preserve_inline_code, text)

    # Escape HTML entities in the rest of the text
    # But we need to be careful not to escape our placeholders
    placeholder_pattern = f"({_CODE_BLOCK_PLACEHOLDER}\\d+{_CODE_BLOCK_PLACEHOLDER}|{_INLINE_CODE_PLACEHOLDER}\\d+{_INLINE_CODE_PLACEHOLDER})"
    parts = re.split(placeholder_pattern, text)
    escaped_parts = []
    for part in parts:
        if part.startswith(_CODE_BLOCK_PLACEHOLDER) or part.startswith(_INLINE_CODE_PLACEHOLDER):
            escaped_parts.append(part)
        else:
            escaped_parts.append(html.escape(part))
    text = "".join(escaped_parts)

    # Convert markdown headers to bold (Telegram doesn't support headers)
    # Handle ### Header, ## Header, # Header
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # Convert unordered lists BEFORE italic conversion to prevent * item from
    # being interpreted as italic markers
    text = re.sub(r"^[\-\*]\s+", "• ", text, flags=re.MULTILINE)

    # Convert bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # Convert italic: *text* or _text_ (but not inside words)
    # Be careful not to match underscores in the middle of words
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)

    # Convert strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # Convert links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Convert ordered lists: 1. item -> keep as is but ensure proper formatting
    # Telegram doesn't have special list support, so we keep numbered format

    # Restore code blocks and inline code
    for placeholder, replacement in code_blocks:
        text = text.replace(placeholder, replacement)

    for placeholder, replacement in inline_codes:
        text = text.replace(placeholder, replacement)

    return text


def split_message_for_telegram(
    text: str, max_length: int = 4096
) -> List[str]:
    """
    Split a long message into chunks suitable for Telegram.

    Tries to split at natural boundaries (newlines, sentences) when possible.
    Preserves HTML tags by not splitting in the middle of them.

    Args:
        text: The text to split
        max_length: Maximum length per chunk (Telegram limit is 4096)

    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Find a good split point
        split_point = max_length

        # Try to split at a newline
        newline_pos = remaining.rfind("\n", 0, max_length)
        if newline_pos > max_length // 2:
            split_point = newline_pos + 1
        else:
            # Try to split at a sentence boundary
            for punct in [". ", "! ", "? "]:
                punct_pos = remaining.rfind(punct, 0, max_length)
                if punct_pos > max_length // 2:
                    split_point = punct_pos + len(punct)
                    break
            else:
                # Try to split at a space
                space_pos = remaining.rfind(" ", 0, max_length)
                if space_pos > max_length // 2:
                    split_point = space_pos + 1

        # Ensure we don't split in the middle of an HTML tag
        # Find the last < before split_point and check if there's a > after it
        last_open = remaining.rfind("<", 0, split_point)
        if last_open != -1:
            last_close = remaining.find(">", last_open, split_point)
            if last_close == -1:
                # We're in the middle of a tag, move split_point before the tag
                split_point = last_open

        chunks.append(remaining[:split_point])
        remaining = remaining[split_point:]

    return chunks
