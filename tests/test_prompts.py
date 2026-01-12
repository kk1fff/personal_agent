"""Tests for prompt generation and template variable injection."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.agent.prompts import (
    get_system_prompt,
    inject_template_variables,
    get_current_datetime,
    SYSTEM_PROMPT,
)


def test_get_current_datetime_utc():
    """Test datetime formatting in UTC."""
    result = get_current_datetime("UTC")
    # Verify format YYYY-MM-DD HH:MM:SS
    assert len(result) == 19
    assert result[4] == '-'
    assert result[7] == '-'
    assert result[10] == ' '
    assert result[13] == ':'
    assert result[16] == ':'
    # Verify it's a valid datetime
    datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_get_current_datetime_with_timezone():
    """Test datetime formatting in non-UTC timezone."""
    result = get_current_datetime("America/New_York")
    assert len(result) == 19
    # Just verify format, not exact time
    datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_inject_template_variables_basic():
    """Test basic template variable injection."""
    template = "Time: {current_datetime}, TZ: {timezone}, Lang: {language}"
    result = inject_template_variables(
        template,
        timezone="America/Los_Angeles",
        language="es",
        inject_datetime=True,
    )
    assert "America/Los_Angeles" in result
    assert "es" in result
    assert "Time:" in result
    assert "{current_datetime}" not in result  # Should be replaced


def test_inject_template_variables_disabled_datetime():
    """Test template injection with datetime disabled."""
    template = "Time: {current_datetime}, TZ: {timezone}"
    result = inject_template_variables(
        template,
        timezone="UTC",
        inject_datetime=False,
    )
    assert "{current_datetime}" in result  # Should NOT be replaced
    assert "UTC" in result


def test_get_system_prompt_default():
    """Test system prompt with default values."""
    result = get_system_prompt()
    assert "UTC" in result
    assert "en" in result
    assert "{current_datetime}" not in result  # Should be replaced
    assert "{timezone}" not in result  # Should be replaced
    assert "{language}" not in result  # Should be replaced


def test_get_system_prompt_with_bot_username():
    """Test system prompt includes bot username."""
    result = get_system_prompt(bot_username="TestBot")
    assert "@TestBot" in result
    assert "Telegram username" in result


def test_get_system_prompt_with_preferences():
    """Test system prompt with custom preferences."""
    result = get_system_prompt(
        bot_username="MyBot",
        timezone="Asia/Tokyo",
        language="ja",
        inject_datetime=True,
    )
    assert "@MyBot" in result
    assert "Asia/Tokyo" in result
    assert "ja" in result


def test_system_prompt_has_placeholders():
    """Test that SYSTEM_PROMPT constant contains placeholders."""
    assert "{current_datetime}" in SYSTEM_PROMPT
    assert "{timezone}" in SYSTEM_PROMPT
    assert "{language}" in SYSTEM_PROMPT


def test_inject_template_variables_preserves_other_content():
    """Test that template injection doesn't break other content."""
    template = "Time: {current_datetime}, Example: some text with braces {not a placeholder}"
    # This should raise KeyError for unknown placeholder
    with pytest.raises(KeyError):
        inject_template_variables(template, inject_datetime=True)


def test_get_current_datetime_various_timezones():
    """Test datetime generation for various timezones."""
    timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
    for tz in timezones:
        result = get_current_datetime(tz)
        assert len(result) == 19
        # Verify it's a valid datetime
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


def test_inject_template_variables_all_defaults():
    """Test template injection with all default parameters."""
    template = "TZ: {timezone}, Lang: {language}, Time: {current_datetime}"
    result = inject_template_variables(template)
    assert "UTC" in result
    assert "en" in result
    assert "{timezone}" not in result
    assert "{language}" not in result
