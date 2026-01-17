"""Tests for message extractor."""

import pytest

from src.config.config_schema import AppConfig, AllowedConversation, AllowedUser, TelegramConfig, LLMConfig, OllamaConfig
from src.telegram.message_extractor import MessageExtractor, ExtractedMessage


@pytest.fixture
def basic_config():
    """Create a basic configuration for testing."""
    return AppConfig(
        telegram=TelegramConfig(bot_token="test_token", mode="poll"),
        llm=LLMConfig(
            provider="ollama",
            ollama=OllamaConfig(model="llama2"),
        ),
    )


@pytest.fixture
def config_with_restrictions():
    """Create a configuration with conversation and user restrictions."""
    return AppConfig(
        telegram=TelegramConfig(bot_token="test_token", mode="poll"),
        allowed_conversations=[
            AllowedConversation(chat_id=123),
            AllowedConversation(chat_id=456),
        ],
        allowed_users=[
            AllowedUser(user_id=789),
        ],
        llm=LLMConfig(
            provider="ollama",
            ollama=OllamaConfig(model="llama2"),
        ),
    )


def test_extract_valid_message(basic_config):
    """Test extracting a valid message."""
    extractor = MessageExtractor(basic_config)
    update = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456, "username": "testuser"},
            "text": "Hello, bot!",
            "message_id": 789,
        }
    }

    extracted = extractor.extract(update)
    assert extracted is not None
    assert extracted.chat_id == 123
    assert extracted.user_id == 456
    assert extracted.message_text == "Hello, bot!"
    assert extracted.message_id == 789
    assert extracted.username == "testuser"


def test_extract_command_message(basic_config):
    """Test extracting a command message."""
    extractor = MessageExtractor(basic_config)
    update = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "/start",
            "message_id": 789,
        }
    }

    extracted = extractor.extract(update)
    assert extracted is not None
    assert extracted.is_command is True


def test_extract_invalid_update(basic_config):
    """Test extracting from invalid update."""
    extractor = MessageExtractor(basic_config)
    update = {"not_a_message": True}

    extracted = extractor.extract(update)
    assert extracted is None


def test_allowed_conversation_check(config_with_restrictions):
    """Test conversation ID filtering."""
    extractor = MessageExtractor(config_with_restrictions)

    assert extractor.is_allowed_conversation(123) is True
    assert extractor.is_allowed_conversation(456) is True
    assert extractor.is_allowed_conversation(999) is False


def test_allowed_user_check(config_with_restrictions):
    """Test user ID filtering."""
    extractor = MessageExtractor(config_with_restrictions)

    assert extractor.is_allowed_user(789) is True
    assert extractor.is_allowed_user(999) is False


def test_extract_with_restrictions(config_with_restrictions):
    """Test extraction with conversation and user restrictions."""
    extractor = MessageExtractor(config_with_restrictions)

    # Allowed conversation and user
    update_allowed = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 789},
            "text": "Hello",
            "message_id": 1,
        }
    }
    assert extractor.extract(update_allowed) is not None

    # Disallowed conversation
    update_disallowed_chat = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 789},
            "text": "Hello",
            "message_id": 1,
        }
    }
    assert extractor.extract(update_disallowed_chat) is None

    # Disallowed user
    update_disallowed_user = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 999},
            "text": "Hello",
            "message_id": 1,
        }
    }
    assert extractor.extract(update_disallowed_user) is None


def test_extract_reply_message(basic_config):
    """Test extracting a reply message with reply_to_message_id."""
    extractor = MessageExtractor(basic_config)
    update = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456, "username": "testuser"},
            "text": "This is a reply",
            "message_id": 789,
            "reply_to_message": {
                "message_id": 788,
                "text": "Original message",
                "from": {"id": 111},
            }
        }
    }

    extracted = extractor.extract(update)
    assert extracted is not None
    assert extracted.reply_to_message_id == 788
    assert extracted.message_text == "This is a reply"


def test_extract_non_reply_message(basic_config):
    """Test extracting a non-reply message has None reply_to_message_id."""
    extractor = MessageExtractor(basic_config)
    update = {
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "Regular message",
            "message_id": 789,
        }
    }

    extracted = extractor.extract(update)
    assert extracted is not None
    assert extracted.reply_to_message_id is None
