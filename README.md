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

### Multi-Agent Orchestrator Mode (Optional)

The system supports an advanced multi-agent architecture where a Dispatcher (Concierge) agent routes requests to specialized agents:

```yaml
agent:
  orchestrator:
    enable: true  # Enable multi-agent mode (default: false)
    # Optional: Override models for specific agents
    # dispatcher_model: "gpt-4"
    # specialist_models:
    #   notion_specialist: "gpt-4"
    #   calendar_specialist: "gpt-3.5-turbo"
```

**How It Works:**

When enabled, the system uses a hierarchical agent structure:

1. **Dispatcher (Concierge)**: Routes incoming requests to the appropriate specialist
   - Handles simple greetings directly ("hi", "hello", "thanks")
   - Never answers substantive questions directly
   - Delegates to specialists based on request type

2. **Specialists**:
   - **Notion Specialist**: Searches and retrieves information from Notion workspace
   - **Calendar Specialist**: Manages Google Calendar (read events, create events)
   - **Memory Specialist**: Recalls past conversations and provides context
   - **Chitchat Specialist**: Handles casual conversation

**Benefits:**

- Cleaner separation of concerns
- Specialists are "blind" to each other's tools
- Better prompt engineering per domain
- Easier to add new capabilities

When `enable: false` (default), the system uses the legacy single-agent mode.

### Notion Intelligence Features (Optional)

The Notion Specialist includes an optional intelligence engine that uses multi-step LLM processing to provide better search results and synthesized answers.

```yaml
agent:
  specialists:
    notion:
      intelligence:
        enabled: true              # Master switch (default: true)
        query_expansion: true      # LLM generates multiple search queries
        llm_reranking: true        # LLM re-ranks results by relevance
        answer_synthesis: true     # LLM synthesizes answer with citations
        max_queries: 3             # Max queries in expansion (1-5)
        rerank_top_n: 10           # Results to consider for re-ranking (1-20)
        fetch_top_n: 3             # Pages to fetch full content (1-10)
```

**How It Works:**

When intelligence is enabled, Notion queries go through a 5-step pipeline:

1. **Intent Analysis**: LLM analyzes the user's question and generates optimal search queries (query expansion)
2. **Execute Searches**: Multiple semantic searches are run against the vector index
3. **Re-rank Results**: LLM scores each result by actual relevance to the question (not just vector similarity)
4. **Fetch Content**: Full page content is fetched for the top-ranked pages
5. **Synthesize Answer**: LLM generates a comprehensive answer with citations and confidence score

**Benefits:**

- **Better Search**: Query expansion finds content that exact keyword matching would miss
- **Higher Relevance**: LLM re-ranking surfaces truly relevant pages over false positives
- **Synthesized Answers**: Get direct answers instead of just page links
- **Citations**: Answers include references to source pages
- **Confidence Scoring**: Know how confident the system is in its answer

**Performance Considerations:**

The full pipeline makes 3 LLM calls per query. You can disable individual steps to reduce latency/cost:

- `query_expansion: false` - Uses the question directly as the search query
- `llm_reranking: false` - Uses vector similarity scores instead of LLM scoring
- `answer_synthesis: false` - Returns raw content instead of synthesized answer
- `enabled: false` - Disables all intelligence, falls back to simple vector search

### Debug Features (Optional)

Enable detailed logging and visualization of agent interactions:

```yaml
debug:
  enable_response_logging: true   # Log each response to separate file
  enable_svg_diagrams: true       # Generate SVG data flow diagrams
  response_log_dir: "logs/responses"  # Directory for response logs
  svg_diagram_dir: "logs/diagrams"    # Directory for SVG files
```

**Response Logging:**

When enabled, each bot response generates a detailed log file at `logs/responses/response_{chat_id}_{timestamp}.log` containing:
- Trace ID
- User message
- Bot response
- All events (tool calls, delegations, LLM interactions, etc.)
- Timing information

**SVG Diagrams:**

When enabled, generates visual sequence diagrams showing how requests flow through the system:
- Shows Dispatcher → Specialist delegations
- Shows tool calls within specialists
- Includes timing information
- Useful for debugging and understanding system behavior

Files are saved to `logs/diagrams/response_{chat_id}_{timestamp}.svg`.

### Web Debug UI (Optional)

A browser-based debug interface with live updates for real-time monitoring:

```yaml
agent:
  debug:
    enable_web_ui: true       # Enable web debug interface
    web_host: "127.0.0.1"     # Host (use 0.0.0.0 for external access)
    web_port: 8765            # Port (1024-65535)
```

**How It Works:**

When enabled, a web server starts alongside the Telegram bot. The URL is displayed in the terminal after "SYSTEM READY":

```
============================================================
✓ SYSTEM READY - Bot is now listening for messages
============================================================
  LLM: gemma3:7b
  Telegram Mode: poll
  Agent Mode: Orchestrator
  Tools: 5 registered
  Debug Web UI: http://127.0.0.1:8765
```

**Built-in Subsections:**

1. **Live Logs**: Real-time log streaming with level filtering (DEBUG, INFO, WARNING, ERROR)
2. **Configuration**: Read-only view of current configuration (secrets are masked)

**Features:**

- Sticky tab bar at the top for switching between subsections
- Responsive design with overflow dropdown for many subsections
- WebSocket connection for live updates (auto-reconnects)
- Modular architecture - add custom subsections without modifying core code

**Adding Custom Subsections:**

Create a new file in `src/web/subsections/` and use the `@subsection` decorator:

```python
from src.web import BaseSubsection, subsection

@subsection
class MyDebugSubsection(BaseSubsection):
    def __init__(self):
        super().__init__(
            name="my-debug",
            display_name="My Debug Panel",
            priority=30,  # Lower = appears first
        )

    async def get_initial_data(self) -> dict:
        return {"status": "ready"}

    async def get_html_template(self) -> str:
        return '<div>Status: <span x-text="data.status"></span></div>'
```

Then import it in `src/web/subsections/__init__.py`.

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
│   ├── agent/                  # Agent system
│   │   ├── agent_processor.py  # Legacy single-agent processor
│   │   ├── base.py             # BaseAgent, AgentContext, AgentResult
│   │   ├── registry.py         # AgentRegistry for specialist lookup
│   │   ├── dispatcher.py       # Dispatcher (Concierge) agent
│   │   ├── specialists/        # Specialist agents
│   │   │   ├── base_specialist.py
│   │   │   ├── notion_specialist.py
│   │   │   ├── calendar_specialist.py
│   │   │   ├── memory_specialist.py
│   │   │   └── chitchat_specialist.py
│   │   └── specialist_prompts/ # System prompts for agents
│   ├── llm/                    # LLM abstraction layer
│   ├── tools/                  # Tool implementations
│   │   ├── agent_tools/        # Agent-as-Tool wrappers
│   │   │   ├── base_agent_tool.py
│   │   │   ├── notion_agent_tool.py
│   │   │   ├── calendar_agent_tool.py
│   │   │   └── memory_agent_tool.py
│   │   └── ...                 # Other tools
│   ├── context/                # Conversation context
│   ├── memory/                 # Vector database
│   ├── debug/                  # Debug infrastructure
│   │   ├── trace.py            # Request tracing
│   │   ├── svg_generator.py    # SVG diagram generation
│   │   └── response_logger.py  # Per-response logging
│   └── utils/                  # Utilities (logging, etc.)
├── tests/                      # Test suite
├── data/                       # Persistent data (auto-created)
│   ├── conversations.db        # SQLite conversation database
│   ├── vector_db/              # Vector database directory
│   └── logs/                   # Log files directory
├── logs/                       # Debug logs (when enabled)
│   ├── responses/              # Per-response log files
│   └── diagrams/               # SVG data flow diagrams
├── config.yaml.example         # Example configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

**Note**: The `data/` folder is automatically created when the application runs. It contains all persistent files including databases, vector stores, and logs. The `logs/` folder for debug features is created when debug options are enabled. Both folders are excluded from version control via `.gitignore`.

## Notion Indexer

The system includes a CLI tool for indexing your Notion workspace. This enables semantic search over your Notion pages.

### Setup

1. Configure your Notion API key and workspaces in `config.yaml`:

```yaml
tools:
  notion:
    api_key: "YOUR_NOTION_API_KEY"
    workspaces:
      - name: "personal"
        root_page_ids:
          - "abc123..."  # Your root page ID
        database_ids: []  # Optional: databases to index
        exclude_page_ids: []  # Pages to skip
        max_depth: 10
```

2. Get your Notion page/database IDs from the URL:
   - Page URL: `https://notion.so/Page-Title-abc123...` → ID is `abc123...`
   - Make sure your Notion integration has access to the pages

### Running the Indexer

Index all configured workspaces:
```bash
python -m src.notion.cli -c config.yaml
```

With verbosity:
```bash
python -m src.notion.cli -c config.yaml -v      # Info level
python -m src.notion.cli -c config.yaml -vv     # Debug level
```

Index a specific workspace:
```bash
python -m src.notion.cli -c config.yaml --workspace personal
```

Preview what would be indexed (dry run):
```bash
python -m src.notion.cli -c config.yaml --dry-run
```

Force reindex all pages (ignore change detection):
```bash
python -m src.notion.cli -c config.yaml --force
```

View index statistics:
```bash
python -m src.notion.cli -c config.yaml --stats
```

### How It Works

1. The indexer traverses your Notion workspace from the configured root pages
2. For each page, it:
   - Builds a breadcrumb path (e.g., "Work > Projects > 2024")
   - Extracts the page content
   - Generates an LLM summary
   - Stores the page in a vector database for semantic search
3. Change detection uses content hashing to skip unchanged pages on subsequent runs
4. After indexing, a workspace summary is generated and saved to `data/notion/info.json`
5. The agent's `notion_search` tool queries this index to find relevant pages

### Workspace Summary and Prompt Injection

When indexing completes, the system generates an overall summary of your Notion workspace. This summary:
- Describes what types of content are in your Notion (projects, notes, ideas, etc.)
- Lists the indexed workspaces and their page counts
- Is automatically injected into the agent's system prompt at startup

This allows the agent to know what content is available in your Notion without needing to perform a search first. For example, the agent can say "I see you have project documentation and meeting notes in your Notion" without you asking.

The summary is stored in `data/notion/info.json`:
```json
{
  "generated_at": "2026-01-24T12:00:00Z",
  "summary": "Your Notion workspace contains 42 indexed pages...",
  "workspaces": [
    {
      "name": "Personal",
      "page_count": 42,
      "topics": ["Projects", "Notes", "Ideas"]
    }
  ]
}
```

To regenerate the summary after adding new content, run the indexer again:
```bash
python -m src.notion.cli -c config.yaml
```

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

