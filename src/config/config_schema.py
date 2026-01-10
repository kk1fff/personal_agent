"""Pydantic models for configuration validation."""

from typing import List, Optional
from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    bot_token: str = Field(..., description="Telegram bot token")
    mode: str = Field(default="poll", description="Mode: 'poll' or 'webhook'")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL (required if mode is webhook)")


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

    conversation_db: str = Field(default="conversations.db", description="Conversation database path")
    vector_db_path: str = Field(default="vector_db", description="Vector database path")


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

