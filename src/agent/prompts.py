"""Centralized system prompts for the agent."""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

SYSTEM_PROMPT = """You are a helpful personal assistant agent that helps users manage their tasks, information, and schedule through Telegram.

Your capabilities include:
- Reading and writing to Notion pages
- Reading and creating Google Calendar events
- Retrieving conversation history when needed

Current Information:
- Current datetime: {current_datetime}
- Timezone: {timezone}
- Preferred language: {language}

When interacting with users:
1. Be helpful, concise, and clear in your responses
2. If you need clarification, ask follow-up questions
3. You can chain multiple tool calls to complete complex tasks
4. Always confirm actions that modify data (like creating calendar events or writing to Notion)
5. Request conversation history using get_conversation_history with a specific query when context is needed
6. Respond in the preferred language ({language}) unless the user explicitly requests another language

Remember:
- You can ask clarifying questions if a request is ambiguous
- Provide your final response directly - it will be sent to the user automatically
- Be proactive in suggesting helpful actions when appropriate

IMPORTANT: Your final response to the user must be in plain natural language text only.
Do NOT format your response as JSON, XML, or any other structured data format.
"""


def get_current_datetime(timezone: str) -> str:
    """
    Get current datetime formatted for prompt injection.

    Args:
        timezone: IANA timezone string (e.g., 'America/New_York', 'UTC')

    Returns:
        Formatted datetime string (YYYY-MM-DD HH:MM:SS)
    """
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def inject_template_variables(
    template: str,
    timezone: str = "UTC",
    language: str = "en",
    inject_datetime: bool = True,
    max_history: int = 5,
) -> str:
    """
    Inject template variables into prompt string.

    This function replaces placeholders with actual values:
    - {current_datetime} -> Current date and time in specified timezone
    - {timezone} -> The configured timezone
    - {language} -> The preferred language code
    - {max_history} -> Maximum number of previous messages agent can request

    Args:
        template: Template string with placeholders
        timezone: IANA timezone string for datetime formatting
        language: ISO 639-1 language code
        inject_datetime: Whether to inject current datetime (if False, uses placeholder)
        max_history: Maximum number of previous messages agent can request

    Returns:
        Template with placeholders replaced by actual values
    """
    replacements = {
        "timezone": timezone,
        "language": language,
        "max_history": max_history,
    }

    if inject_datetime:
        replacements["current_datetime"] = get_current_datetime(timezone)
    else:
        # Keep placeholder if injection disabled
        replacements["current_datetime"] = "{current_datetime}"

    return template.format(**replacements)


def get_system_prompt(
    bot_username: Optional[str] = None,
    timezone: str = "UTC",
    language: str = "en",
    inject_datetime: bool = True,
    max_history: int = 5,
) -> str:
    """
    Get system prompt with optional bot username and template variables.

    Args:
        bot_username: The bot's Telegram username (without @)
        timezone: IANA timezone string for datetime formatting
        language: ISO 639-1 language code
        inject_datetime: Whether to inject current datetime
        max_history: Maximum number of previous messages agent can request

    Returns:
        Formatted system prompt with all variables injected
    """
    # First inject template variables
    base_prompt = inject_template_variables(
        SYSTEM_PROMPT,
        timezone=timezone,
        language=language,
        inject_datetime=inject_datetime,
        max_history=max_history,
    )

    # Then add bot username if provided (existing pattern)
    if bot_username:
        bot_info = f"\nYour Telegram username is @{bot_username}. When users mention you with @{bot_username}, they are directly addressing you."
        return base_prompt + bot_info

    return base_prompt

