"""Configuration loader for YAML files."""

import yaml
from pathlib import Path
from typing import Optional

from .config_schema import AppConfig


class ConfigLoader:
    """Load and validate configuration from YAML files."""

    @staticmethod
    def load_config(path: str = "config.yaml") -> AppConfig:
        """
        Load configuration from YAML file.

        Args:
            path: Path to configuration file

        Returns:
            Validated AppConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        if not config_dict:
            raise ValueError("Configuration file is empty")

        config = AppConfig(**config_dict)
        config.validate()

        return config

    @staticmethod
    def validate_config(config: dict) -> bool:
        """
        Validate configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            True if valid

        Raises:
            ValueError: If config is invalid
        """
        app_config = AppConfig(**config)
        app_config.validate()
        return True


def load_config(path: str = "config.yaml") -> AppConfig:
    """
    Convenience function to load configuration.

    Args:
        path: Path to configuration file

    Returns:
        Validated AppConfig instance
    """
    return ConfigLoader.load_config(path)

