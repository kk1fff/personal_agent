"""Pydantic models for configuration validation."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    bot_token: str = Field(..., description="Telegram bot token")
    mode: str = Field(default="poll", description="Mode: 'poll' or 'webhook'")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL (required if mode is webhook)")
    require_mention: bool = Field(default=False, description="Only respond when bot is @mentioned")
    bot_username: Optional[str] = Field(default=None, description="Bot username (auto-detected if not provided)")


class AllowedConversation(BaseModel):
    """Allowed conversation configuration."""

    chat_id: int = Field(..., description="Telegram chat ID")


class AllowedUser(BaseModel):
    """Allowed user configuration."""

    user_id: int = Field(..., description="Telegram user ID")


class OllamaConfig(BaseModel):
    """Ollama LLM configuration."""

    base_url: str = Field(default="http://localhost:11434", description="Ollama base URL")
    model: str = Field(..., description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, gt=0, description="Maximum tokens")
    context_window: Optional[int] = Field(default=None, description="Context window size")


class OpenAIConfig(BaseModel):
    """OpenAI LLM configuration."""

    api_key: str = Field(..., description="OpenAI API key")
    model: str = Field(default="gpt-3.5-turbo", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, gt=0, description="Maximum tokens")
    organization_id: Optional[str] = Field(default=None, description="Organization ID")


class GeminiConfig(BaseModel):
    """Gemini LLM configuration."""

    api_key: str = Field(..., description="Gemini API key")
    model: str = Field(default="gemini-pro", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(default=2048, gt=0, description="Maximum tokens")
    safety_settings: Optional[dict] = Field(default=None, description="Safety settings")


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = Field(..., description="Provider: 'ollama', 'openai', or 'gemini'")
    ollama: Optional[OllamaConfig] = Field(default=None, description="Ollama configuration")
    openai: Optional[OpenAIConfig] = Field(default=None, description="OpenAI configuration")
    gemini: Optional[GeminiConfig] = Field(default=None, description="Gemini configuration")


class NotionConfig(BaseModel):
    """Notion tool configuration."""

    api_key: str = Field(..., description="Notion API key")


class GoogleCalendarConfig(BaseModel):
    """Google Calendar tool configuration."""

    credentials_path: Optional[str] = Field(default=None, description="Path to credentials JSON file")
    service_account_email: Optional[str] = Field(default=None, description="Service account email")
    service_account_key: Optional[str] = Field(default=None, description="Service account key")


class ToolsConfig(BaseModel):
    """Tools configuration."""

    notion: Optional[NotionConfig] = Field(default=None, description="Notion configuration")
    google_calendar: Optional[GoogleCalendarConfig] = Field(
        default=None, description="Google Calendar configuration"
    )


class DatabaseConfig(BaseModel):
    """Database configuration."""

    conversation_db: str = Field(default="data/conversations.db", description="Conversation database path")
    vector_db_path: str = Field(default="data/vector_db", description="Vector database path")


class AgentPreferencesConfig(BaseModel):
    """Agent preferences configuration."""

    timezone: str = Field(
        default="UTC",
        description="Default timezone (e.g., 'America/New_York', 'UTC', 'Asia/Tokyo')"
    )
    language: str = Field(
        default="en",
        description="Preferred response language (ISO 639-1 code, e.g., 'en', 'zh', 'es')"
    )

    @model_validator(mode='after')
    def validate_timezone(self) -> 'AgentPreferencesConfig':
        """Validate timezone string using zoneinfo."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError(
                f"Invalid timezone: '{self.timezone}'. "
                f"Must be a valid IANA timezone (e.g., 'America/New_York', 'UTC', 'Asia/Tokyo')"
            )
        return self

    @field_validator('language')
    @classmethod
    def validate_language_code(cls, v: str) -> str:
        """Validate language code is 2-letter ISO 639-1 code."""
        if not v or len(v) != 2 or not v.isalpha():
            raise ValueError(
                f"Invalid language code: '{v}'. "
                f"Must be a 2-letter ISO 639-1 code (e.g., 'en', 'zh', 'es')"
            )
        return v.lower()


class ContextConfig(BaseModel):
    """Context manager configuration."""

    max_history: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of previous messages agent can request"
    )


class AgentConfig(BaseModel):
    """Agent configuration."""

    preferences: AgentPreferencesConfig = Field(
        default_factory=AgentPreferencesConfig,
        description="Agent preferences (timezone, language, etc.)"
    )
    inject_datetime: bool = Field(
        default=True,
        description="Whether to inject current datetime into prompts"
    )
    context: ContextConfig = Field(
        default_factory=ContextConfig,
        description="Context manager configuration"
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    telegram: TelegramConfig = Field(..., description="Telegram configuration")
    allowed_conversations: List[AllowedConversation] = Field(
        default_factory=list, description="Allowed conversation IDs"
    )
    allowed_users: List[AllowedUser] = Field(default_factory=list, description="Allowed user IDs")
    llm: LLMConfig = Field(..., description="LLM configuration")
    tools: ToolsConfig = Field(default_factory=ToolsConfig, description="Tools configuration")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database configuration")
    agent: AgentConfig = Field(
        default_factory=AgentConfig,
        description="Agent configuration and preferences"
    )

    def validate(self) -> None:
        """Validate configuration consistency."""
        if self.telegram.mode == "webhook" and not self.telegram.webhook_url:
            raise ValueError("webhook_url is required when mode is 'webhook'")

        provider_configs = {
            "ollama": self.llm.ollama,
            "openai": self.llm.openai,
            "gemini": self.llm.gemini,
        }

        if self.llm.provider not in provider_configs:
            raise ValueError(f"Unknown LLM provider: {self.llm.provider}")

        if not provider_configs[self.llm.provider]:
            raise ValueError(f"{self.llm.provider} configuration is required when provider is '{self.llm.provider}'")

