# Personal Agent System

A Telegram bot powered by AI agents that helps users manage tasks, information, and schedules. The system supports multiple LLM providers (Ollama, ChatGPT, Gemini) and includes tools for Notion and Google Calendar integration.

## Features

- **Telegram Integration**: Support for both polling and webhook modes
- **Multi-LLM Support**: Works with Ollama (local), OpenAI (ChatGPT), and Google Gemini
- **Pluggable Tool System**: Extensible tools including Notion and Google Calendar integration
- **Conversation Management**: SQLite-based conversation history with context retrieval
- **Vector Memory**: Optional vector database for long-term memory and semantic search
- **Configurable**: YAML-based configuration with credential management

## Prerequisites

- Python 3.8 or higher
- Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))
- LLM API credentials (depending on your chosen provider):
  - Ollama: Local installation (optional, for local LLM)
  - OpenAI: API key for ChatGPT
  - Gemini: API key for Google Gemini

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd personal_agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the example configuration:
```bash
cp config.yaml.example config.yaml
```

4. Edit `config.yaml` and fill in your credentials:
   - Telegram bot token
   - LLM provider and credentials
   - Allowed conversation IDs and user IDs
   - Tool credentials (Notion, Google Calendar) if needed

## Configuration

The `config.yaml` file contains all system configuration. Key sections:

- **telegram**: Bot token and mode (poll/webhook)
- **allowed_conversations**: List of Telegram chat IDs the bot will respond to
- **allowed_users**: List of Telegram user IDs allowed to use the bot
- **llm**: LLM provider configuration (ollama, openai, or gemini)
- **tools**: Tool-specific credentials (Notion, Google Calendar)
- **database**: Database file paths

See `config.yaml.example` for a complete example with all options.

### Agent Preferences

Configure agent behavior and prompt variables in the `agent` section:

```yaml
agent:
  preferences:
    # Timezone for datetime awareness (IANA timezone names)
    timezone: "America/New_York"  # Default: "UTC"

    # Preferred response language (ISO 639-1 codes)
    language: "en"  # Default: "en" (English)

  # Enable/disable current datetime injection into prompts
  inject_datetime: true  # Default: true
```

**Available Timezone Examples:**
- `"UTC"` - Coordinated Universal Time
- `"America/New_York"` - Eastern Time (US)
- `"America/Los_Angeles"` - Pacific Time (US)
- `"Europe/London"` - British Time
- `"Asia/Tokyo"` - Japan Standard Time
- `"Australia/Sydney"` - Australian Eastern Time

See the [full list of timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

**Common Language Codes:**
- `"en"` - English
- `"es"` - Spanish
- `"zh"` - Chinese
- `"fr"` - French
- `"de"` - German
- `"ja"` - Japanese
- `"ko"` - Korean

**How It Works:**

The agent's system prompt includes dynamic information:
- Current date and time in your configured timezone
- Timezone setting (helps agent understand scheduling context)
- Preferred language (agent will respond in this language by default)

This helps the agent provide more contextual and time-aware responses.

### Conversation History Management

Configure how agents access conversation history in the `agent.context` section:

```yaml
agent:
  context:
    # Maximum number of previous messages agent can request
    max_history: 5  # Range: 1-50, Default: 5
```

**How It Works:**

By default, agents receive only the current user message WITHOUT automatic conversation history. This design:
- Reduces token usage and processing time
- Gives agents explicit control over when they need context
- Prevents unnecessary history loading for simple requests

**Retrieving History:**

When an agent needs context from previous messages, it uses the `get_conversation_history` tool.
- The tool uses the `llm` mode to generate a summarized context relevant to a specific query.
- It requires a `query` parameter to identify what information to look for.

History is retrieved on-demand only when needed.

**Example Scenarios:**

- **Simple requests** ("What's 2+2?"): No history needed, agent responds immediately
- **Follow-up questions** ("What did I ask you earlier?"): Agent uses `get_conversation_history` to retrieve context
- **Multi-turn tasks**: Agent requests history to maintain continuity across conversation

**Configuration Tips:**

- Set `max_history: 3-5` for most use cases (balances context vs. token usage)
- Increase to `10-20` if your agent handles complex multi-turn conversations
- Lower to `1-3` for simple Q&A bots to minimize costs

### @Mention Filtering (Optional)

Control when the bot responds to messages in group chats:

```yaml
telegram:
  bot_token: "YOUR_TOKEN"
  mode: "poll"
  require_mention: true  # Enable @mention filtering
  # bot_username: "YourBotName"  # Optional - auto-detected if omitted
```

When `require_mention: true`:
- Bot stores ALL messages in allowed conversations (maintains full conversation context)
- Bot only RESPONDS to messages that @mention it (e.g., "@BotName hello")
- Non-mentioned messages are saved to database but don't trigger a response
- Useful in group chats to prevent spam responses while maintaining conversation awareness
- Bot username is auto-detected from Telegram API if not configured

When `require_mention: false` (default):
- Bot responds to all messages in allowed conversations
- Traditional behavior for 1-on-1 chats

## Launching the System

### Basic Launch

Run the system with default settings:
```bash
python -m src.main
```

Or specify a custom config file:
```bash
python -m src.main /path/to/config.yaml
```

### Startup Information

When the system starts, it displays detailed status information including:

1. **Configuration Loading** - Shows the config file being used
2. **Database Initialization** - Displays database paths and initialization status
3. **Context Manager** - Confirms context management is ready
4. **Vector Store** - Shows vector database path and memory feature status
5. **LLM Initialization** - Displays:
   - Provider (Ollama, OpenAI, or Gemini)
   - Model name
   - Base URL (for Ollama)
   - Temperature setting
   - Max tokens
   - Context window size (if applicable)
6. **Telegram Client** - Shows connection mode (poll/webhook)
7. **Tools Registration** - Lists all registered tools with their descriptions
8. **System Ready** - Final confirmation showing:
   - LLM model in use
   - Connection mode
   - Number of registered tools

Example startup output:
```
============================================================
Personal Agent System - Starting
============================================================
[1/7] Loading configuration from: config.yaml
✓ Configuration loaded successfully
[2/7] Initializing conversation database
  Database path: data/conversations.db
✓ Conversation database ready
...
============================================================
✓ SYSTEM READY - Bot is now listening for messages
============================================================
  LLM: gemma3:7b
  Mode: poll
  Tools: 5 registered

Press Ctrl+C to stop
============================================================
```

### Verbosity Levels

Control logging verbosity using `-v`, `-vv`, or `-vvv` flags:

- **No flag** (default): WARNING level - only warnings and errors
- **-v**: INFO level - informational messages (recommended for normal operation)
- **-vv**: DEBUG level - detailed debugging information
- **-vvv**: DEBUG level with maximum detail

Examples:
```bash
# Info level logging (shows startup details and message processing)
python -m src.main -v

# Debug level logging (shows detailed internal operations)
python -m src.main -vv

# Maximum verbosity (includes all debug information)
python -m src.main -vvv config.yaml
```

### Log Files

By default, all logs are saved to `data/logs/log_YYYYMMDD_HHMMSS.log` with timestamps in local time. Log files include:
- All log levels (regardless of console verbosity)
- Function names and line numbers
- Detailed timestamps

Log files are automatically created in the `data/logs/` directory.

## Testing

### Prerequisites for Testing

Make sure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Running Tests

Run all tests:
```bash
pytest tests/
```

Run tests with verbosity:
```bash
pytest tests/ -v
```

Run a specific test file:
```bash
pytest tests/test_config_loader.py
```

Run a specific test:
```bash
pytest tests/test_config_loader.py::test_load_config_valid
```

### Test Coverage

Install coverage tools:
```bash
pip install pytest-cov
```

Run tests with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Test Structure

Tests are organized by module:
- `test_config_loader.py`: Configuration loading and validation
- `test_message_extractor.py`: Telegram message extraction and filtering
- `test_conversation_db.py`: Database operations
- `test_context_manager.py`: Conversation context management
- `test_tools_base.py`: Base tool functionality
- `test_tool_registry.py`: Tool registration and initialization

## Project Structure

```
personal_agent/
├── src/
│   ├── main.py                 # Entry point
│   ├── config/                 # Configuration management
│   ├── telegram/               # Telegram integration
│   ├── agent/                  # Agent processor
│   ├── llm/                    # LLM abstraction layer
│   ├── tools/                  # Tool implementations
│   ├── context/                # Conversation context
│   ├── memory/                 # Vector database
│   └── utils/                  # Utilities (logging, etc.)
├── tests/                      # Test suite
├── data/                       # Persistent data (auto-created)
│   ├── conversations.db        # SQLite conversation database
│   ├── vector_db/              # Vector database directory
│   └── logs/                   # Log files directory
├── config.yaml.example         # Example configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

**Note**: The `data/` folder is automatically created when the application runs. It contains all persistent files including databases, vector stores, and logs. This folder is excluded from version control via `.gitignore`.

## Usage

Once the bot is running:

1. Start a conversation with your bot on Telegram
2. Send messages - the bot will process them through the AI agent
3. The agent can:
   - Answer questions
   - Read and write to Notion pages
   - Read and create Google Calendar events
   - Ask follow-up questions for clarification
   - Chain multiple tool calls for complex tasks

## Development

### Adding New Tools

1. Create a new tool class inheriting from `BaseTool` in `src/tools/`
2. Implement `execute()`, `get_schema()`, and optionally `validate_input()`
3. Register the tool in `ToolRegistry.initialize_tools()`

### Adding New LLM Providers

1. Create a new LLM class inheriting from `BaseLLM` in `src/llm/`
2. Implement `generate()`, `stream_generate()`, and `get_model_name()`
3. Add provider configuration to `config_schema.py`
4. Add provider creation logic to `create_llm()` in `main.py`

## Troubleshooting

### Bot Not Responding

- Check that your bot token is correct
- Verify the chat ID is in `allowed_conversations`
- Check logs for error messages

### LLM Errors

- Verify API keys are correct
- Check network connectivity
- For Ollama, ensure the service is running locally

### Database Errors

- Ensure write permissions in the project directory (specifically for the `data/` folder)
- Check that SQLite is available
- Verify the `data/` directory can be created automatically

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

