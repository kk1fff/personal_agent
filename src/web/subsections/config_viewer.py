"""Configuration viewer subsection."""

import json
from typing import Any, Dict, Optional

from ..base import BaseSubsection
from ..registry import subsection

# Global config reference
_config: Optional[Any] = None


def set_config(config: Any) -> None:
    """Set the global config reference for the viewer."""
    global _config
    _config = config


def get_config() -> Optional[Any]:
    """Get the global config reference."""
    return _config


def config_to_display_dict(config: Any) -> Dict[str, Any]:
    """Convert config to a display-safe dictionary (masks secrets)."""
    if config is None:
        return {}

    try:
        # Convert Pydantic model to dict
        if hasattr(config, "model_dump"):
            config_dict = config.model_dump()
        elif hasattr(config, "dict"):
            config_dict = config.dict()
        else:
            config_dict = dict(config)

        # Mask sensitive fields
        def mask_secrets(obj: Any, path: str = "") -> Any:
            if isinstance(obj, dict):
                masked = {}
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    # Mask fields that likely contain secrets
                    if any(
                        secret in key.lower()
                        for secret in ["token", "key", "secret", "password", "credential"]
                    ):
                        if isinstance(value, str) and len(value) > 4:
                            masked[key] = value[:4] + "*" * (len(value) - 4)
                        elif value:
                            masked[key] = "***"
                        else:
                            masked[key] = value
                    else:
                        masked[key] = mask_secrets(value, current_path)
                return masked
            elif isinstance(obj, list):
                return [mask_secrets(item, path) for item in obj]
            return obj

        return mask_secrets(config_dict)
    except Exception as e:
        return {"error": f"Failed to serialize config: {str(e)}"}


@subsection
class ConfigViewerSubsection(BaseSubsection):
    """Read-only configuration viewer subsection."""

    def __init__(self):
        super().__init__(
            name="config",
            display_name="Configuration",
            priority=20,
            icon="",
        )

    async def get_initial_data(self) -> Dict[str, Any]:
        """Get initial config data."""
        config = get_config()
        config_dict = config_to_display_dict(config)

        return {
            "config": config_dict,
            "config_json": json.dumps(config_dict, indent=2, default=str),
        }

    async def get_html_template(self) -> str:
        """Get HTML template for config viewer."""
        return '''
<div class="config-viewer">
    <h3>Current Configuration (Read-Only)</h3>
    <p style="color: #6b7280; font-size: 13px; margin-bottom: 16px;">
        Sensitive values (tokens, keys, secrets) are masked for security.
    </p>
    <div class="config-content">
        <pre x-text="data.config_json"></pre>
    </div>
</div>
'''
