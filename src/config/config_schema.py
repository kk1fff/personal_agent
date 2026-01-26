"""Pydantic models for configuration validation."""

from typing import Dict, List, Optional
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


class NotionWorkspaceConfig(BaseModel):
    """Configuration for a single Notion workspace to index."""

    name: str = Field(..., description="Friendly name for this workspace")
    root_page_ids: List[str] = Field(
        default_factory=list,
        description="List of root page IDs to start indexing from",
    )
    database_ids: List[str] = Field(
        default_factory=list,
        description="List of database IDs to index",
    )
    exclude_page_ids: List[str] = Field(
        default_factory=list,
        description="Page IDs to exclude from indexing",
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum depth to traverse in page hierarchy",
    )


class NotionConfig(BaseModel):
    """Notion tool configuration."""

    api_key: str = Field(..., description="Notion API key")
    workspaces: List[NotionWorkspaceConfig] = Field(
        default_factory=list,
        description="List of workspaces to index",
    )
    index_collection: str = Field(
        default="notion_pages",
        description="ChromaDB collection name for Notion index",
    )
    rate_limit_delay: float = Field(
        default=0.35,
        ge=0.1,
        le=5.0,
        description="Delay between Notion API calls in seconds",
    )
    search_results_default: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Default number of search results to return",
    )


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
    time_gap_threshold_minutes: int = Field(
        default=60,
        ge=15,
        le=180,
        description="Time gap (minutes) that defines session boundary for smart context"
    )
    lookback_limit: int = Field(
        default=25,
        ge=10,
        le=100,
        description="Maximum messages to inspect when clustering"
    )
    message_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum recent references to pull for LLM summarization"
    )


class OrchestratorConfig(BaseModel):
    """Multi-agent orchestrator configuration."""

    enable: bool = Field(
        default=False,
        description="Enable multi-agent orchestrator pattern (dispatcher + specialists)"
    )
    dispatcher_model: Optional[str] = Field(
        default=None,
        description="Override LLM model for dispatcher (uses main LLM if not set)"
    )
    specialist_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Override LLM models per specialist (e.g., {'notion': 'gpt-4'})"
    )


class NotionIntelligenceConfig(BaseModel):
    """Configuration for Notion specialist intelligence features."""

    enabled: bool = Field(
        default=True,
        description="Master switch for intelligence features"
    )
    query_expansion: bool = Field(
        default=True,
        description="Enable LLM-based query expansion (generates multiple search queries)"
    )
    llm_reranking: bool = Field(
        default=True,
        description="Enable LLM-based result re-ranking (scores results by relevance)"
    )
    answer_synthesis: bool = Field(
        default=True,
        description="Enable LLM-based answer synthesis (generates answer with citations)"
    )
    max_queries: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum queries in query expansion"
    )
    rerank_top_n: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of results to consider for re-ranking"
    )
    fetch_top_n: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of top pages to fetch full content"
    )


class NotionSpecialistConfig(BaseModel):
    """Configuration for Notion specialist agent."""

    intelligence: NotionIntelligenceConfig = Field(
        default_factory=NotionIntelligenceConfig,
        description="Intelligence features configuration"
    )


class SpecialistsConfig(BaseModel):
    """Configuration for specialist agents."""

    notion: NotionSpecialistConfig = Field(
        default_factory=NotionSpecialistConfig,
        description="Notion specialist configuration"
    )


class DebugConfig(BaseModel):
    """Debug and logging configuration."""

    enable_response_logging: bool = Field(
        default=False,
        description="Create separate log file for each Telegram response"
    )
    enable_svg_diagrams: bool = Field(
        default=False,
        description="Generate SVG data flow diagrams for each response"
    )
    response_log_dir: str = Field(
        default="logs/responses",
        description="Directory for per-response log files"
    )
    svg_diagram_dir: str = Field(
        default="logs/diagrams",
        description="Directory for SVG diagram files"
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
    orchestrator: OrchestratorConfig = Field(
        default_factory=OrchestratorConfig,
        description="Multi-agent orchestrator configuration"
    )
    specialists: SpecialistsConfig = Field(
        default_factory=SpecialistsConfig,
        description="Specialist agents configuration"
    )
    debug: DebugConfig = Field(
        default_factory=DebugConfig,
        description="Debug and logging configuration"
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

