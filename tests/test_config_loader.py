"""Tests for configuration loader."""

import pytest
import yaml
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.config.config_loader import ConfigLoader, load_config
from src.config.config_schema import AppConfig


def test_load_config_valid():
    """Test loading a valid configuration."""
    config_dict = {
        "telegram": {
            "bot_token": "test_token",
            "mode": "poll",
        },
        "llm": {
            "provider": "ollama",
            "ollama": {
                "model": "llama2",
                "base_url": "http://localhost:11434",
            },
        },
    }

    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)
        assert isinstance(config, AppConfig)
        assert config.telegram.bot_token == "test_token"
        assert config.telegram.mode == "poll"
        assert config.llm.provider == "ollama"
    finally:
        Path(config_path).unlink()


def test_load_config_missing_file():
    """Test loading a non-existent configuration file."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")


def test_load_config_invalid():
    """Test loading an invalid configuration."""
    config_dict = {
        "telegram": {
            "bot_token": "test_token",
            # Missing mode
        },
        "llm": {
            "provider": "ollama",
            # Missing ollama config
        },
    }

    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        with pytest.raises(Exception):  # Should raise validation error
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_validate_config():
    """Test configuration validation."""
    config_dict = {
        "telegram": {
            "bot_token": "test_token",
            "mode": "poll",
        },
        "llm": {
            "provider": "ollama",
            "ollama": {
                "model": "llama2",
            },
        },
    }

    assert ConfigLoader.validate_config(config_dict) is True


def test_validate_config_webhook_requires_url():
    """Test that webhook mode requires webhook_url."""
    config_dict = {
        "telegram": {
            "bot_token": "test_token",
            "mode": "webhook",
            # Missing webhook_url
        },
        "llm": {
            "provider": "ollama",
            "ollama": {
                "model": "llama2",
            },
        },
    }

    with pytest.raises(ValueError, match="webhook_url"):
        config = AppConfig(**config_dict)
        config.validate()


def test_load_config_with_agent_preferences():
    """Test loading configuration with agent preferences."""
    config_dict = {
        "telegram": {"bot_token": "test_token", "mode": "poll"},
        "llm": {"provider": "ollama", "ollama": {"model": "llama2"}},
        "agent": {
            "preferences": {
                "timezone": "America/New_York",
                "language": "es"
            },
            "inject_datetime": True
        }
    }

    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.agent.preferences.timezone == "America/New_York"
        assert config.agent.preferences.language == "es"
        assert config.agent.inject_datetime is True
    finally:
        Path(config_path).unlink()


def test_load_config_without_agent_section():
    """Test loading configuration without agent section (backward compatibility)."""
    config_dict = {
        "telegram": {"bot_token": "test_token", "mode": "poll"},
        "llm": {"provider": "ollama", "ollama": {"model": "llama2"}},
    }

    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)
        # Should use defaults
        assert config.agent.preferences.timezone == "UTC"
        assert config.agent.preferences.language == "en"
        assert config.agent.inject_datetime is True
    finally:
        Path(config_path).unlink()


def test_invalid_timezone():
    """Test that invalid timezone raises validation error."""
    config_dict = {
        "telegram": {"bot_token": "test_token", "mode": "poll"},
        "llm": {"provider": "ollama", "ollama": {"model": "llama2"}},
        "agent": {
            "preferences": {"timezone": "Invalid/Timezone"}
        }
    }

    with pytest.raises(ValueError, match="Invalid timezone"):
        AppConfig(**config_dict)


def test_invalid_language_code():
    """Test that invalid language code raises validation error."""
    config_dict = {
        "telegram": {"bot_token": "test_token", "mode": "poll"},
        "llm": {"provider": "ollama", "ollama": {"model": "llama2"}},
        "agent": {
            "preferences": {"language": "invalid_code"}
        }
    }

    with pytest.raises(ValueError, match="Invalid language code"):
        AppConfig(**config_dict)


def test_valid_language_codes():
    """Test that valid 2-letter language codes are accepted."""
    config_dict_template = {
        "telegram": {"bot_token": "test_token", "mode": "poll"},
        "llm": {"provider": "ollama", "ollama": {"model": "llama2"}},
        "agent": {
            "preferences": {"language": None}  # Will be replaced
        }
    }

    valid_codes = ["en", "es", "zh", "fr", "de", "ja", "ko", "EN", "ES"]  # Include uppercase
    for code in valid_codes:
        config_dict = config_dict_template.copy()
        config_dict["agent"]["preferences"]["language"] = code
        config = AppConfig(**config_dict)
        # Should be lowercased
        assert config.agent.preferences.language == code.lower()

