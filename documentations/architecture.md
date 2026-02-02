# Personal Agent System - Architecture Documentation

## Overview

The Personal Agent System is a Telegram bot that processes user commands through an AI agent powered by configurable LLM backends. The system extracts messages from Telegram, routes them through an agent processor that can invoke various tools, maintains conversation history, and responds back to users. The architecture supports multiple LLM providers (Ollama, ChatGPT, Gemini), implements a pluggable tool system, and manages conversation context per chat.

## Goal

Create a flexible, extensible personal assistant bot that:
- Integrates seamlessly with Telegram for user interaction
- Supports multiple LLM backends for flexibility
- Provides extensible tool system for various integrations (Notion, Google Calendar, etc.)
- Maintains conversation context for coherent multi-turn interactions
- Supports chained tasks and follow-up questions
- Is easily configurable and testable

## High-Level Design

The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐
│   Telegram      │
│   (External)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Client │◄───┐
│ (Poll/Webhook)  │    │
└────────┬────────┘    │
         │              │
         ▼              │
┌─────────────────┐    │
│ Message         │    │
│ Extractor       │    │
└────────┬────────┘    │
         │              │
         ▼              │
┌─────────────────┐    │
│ Conversation    │    │
│ Context Manager │    │
└────────┬────────┘    │
         │              │
         ▼              │
┌─────────────────┐    │
│ Agent Processor │    │
│ (pydantic_ai)   │    │
└────────┬────────┘    │
         │              │
    ┌────┴────┐         │
    │         │         │
    ▼         ▼         │
┌───────┐ ┌──────────┐  │
│  LLM  │ │  Tools  │  │
│ Layer │ │ Registry │  │
└───────┘ └──────────┘  │
                        │
         ┌──────────────┘
         │
         ▼
┌─────────────────┐
│ Response        │
│ Handler         │
└─────────────────┘
```

### Data Flow

1. **Message Reception**: Telegram messages arrive via poll or webhook
2. **Validation**: Message extractor validates chat/user IDs against configuration
3. **Mention Detection**: Check if bot is @mentioned (sets is_mentioned flag)
4. **Storage**: ALL valid messages stored in SQLite with raw JSON
5. **Response Decision**: Only respond if bot was mentioned (when enabled)
6. **Context Creation**: Empty context created (no automatic history - agent must request via tool)
7. **Agent Processing**: Agent processes message with LLM and tools (if responding)
8. **Tool Execution**: Tools execute with conversation context when needed
9. **Response**: Agent response sent to Telegram and stored

## Constraints

- **Python 3.8+**: Minimum Python version requirement
- **Async/Await**: All I/O operations use async/await for concurrency
- **Configuration-Driven**: System behavior controlled via YAML configuration, including agent preferences (timezone, language) and prompt variable injection
- **Credential Security**: Credentials stored in config.yaml (excluded from git)
- **Single Process**: Designed to run as a single process (can be scaled horizontally)

## Design Principles

1. **Modularity**: Each component is self-contained with clear interfaces
2. **Extensibility**: New tools and LLM providers can be added without modifying core code
3. **Testability**: Core modules designed to be easily testable with dependency injection
4. **Configuration Over Code**: Behavior controlled via YAML configuration
5. **Separation of Concerns**: Clear boundaries between layers (telegram, agent, tools, storage)
6. **Error Handling**: Graceful error handling with logging at appropriate levels
7. **Type Safety**: Use of type hints and Pydantic for validation

## Modules

### 1. Configuration Module (`src/config/`)
- **Purpose**: Load and validate YAML configuration
- **Key Components**:
  - `config_loader.py`: YAML loading and validation
  - `config_schema.py`: Pydantic models for configuration validation including agent preferences
- **Dependencies**: `pyyaml`, `pydantic`, `zoneinfo` (standard library)

### 2. Telegram Integration (`src/telegram/`)
- **Purpose**: Handle Telegram bot communication
- **Key Components**:
  - `client.py`: Main Telegram client wrapper
  - `poll_handler.py`: Polling mode handler
  - `webhook_handler.py`: Webhook mode handler
  - `message_extractor.py`: Message extraction, validation, and @mention detection
- **Dependencies**: `python-telegram-bot`

#### Message Filtering and Response Control

- **Conversation Filtering**: Only allowed chat_ids and user_ids are processed
- **@Mention Detection**: Optionally require bot @mention to respond
- **Full Context Storage**: ALL messages stored regardless of mention status
- **Selective Response**: Bot only responds to @mentioned messages (when enabled)
- **Auto-Detection**: Bot username automatically detected from Telegram API

### 3. Agent Processor (`src/agent/`)
- **Purpose**: Core AI agent orchestration
- **Key Components**:
  - `agent_processor.py`: Main agent processing logic using pydantic_ai
  - `prompts.py`: Centralized system prompts with template variable injection
- **Dependencies**: `pydantic-ai`

#### Prompt Variable Injection

System prompts support template variables that are replaced at runtime:
- Variables configured globally in `config.yaml` under `agent.preferences`
- Timezone-aware datetime injection using Python's `zoneinfo`
- Language preference for multilingual support
- Template replacement in `prompts.py` using safe string formatting

### 4. LLM Abstraction Layer (`src/llm/`)
- **Purpose**: Unified interface for multiple LLM providers
- **Key Components**:
  - `base.py`: Abstract base class for LLM implementations
  - `ollama_llm.py`: Ollama (local LLM) implementation
  - `openai_llm.py`: OpenAI (ChatGPT) implementation
  - `gemini_llm.py`: Google Gemini implementation
- **Dependencies**: `ollama`, `openai`, `google-genai`

### 5. Tool System (`src/tools/`)
- **Purpose**: Pluggable tool system for extending agent capabilities
- **Key Components**:
  - `base.py`: Base tool interface
  - `context_manager.py`: Conversation history retrieval tool
  - `notion_search.py`: Notion semantic search and page reading tool
  - `calendar_reader.py`: Google Calendar reading tool
  - `calendar_writer.py`: Google Calendar writing tool
  - `registry.py`: Centralized tool registry
- **Dependencies**: `notion-client`, `google-api-python-client`, `google-auth`

### 5.1 Notion Module (`src/notion/`)
- **Purpose**: Notion workspace indexing and search capabilities
- **Key Components**:
  - `client.py`: Notion API wrapper with page/block traversal
  - `models.py`: Data models for Notion pages and indexing
  - `traversal.py`: Workspace hierarchy traversal
  - `indexer.py`: LLM-powered indexer with summary generation
  - `cli.py`: Command-line interface for indexing
- **Dependencies**: `notion-client`, `chromadb`, `sentence-transformers`

#### Notion Indexing Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                          │
│                   (src/notion/cli.py)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   NotionIndexer                             │
│                (src/notion/indexer.py)                      │
│  - Orchestrates indexing process                            │
│  - Generates LLM summaries                                  │
│  - Stores in vector database                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
┌─────────────┐ ┌───────────┐ ┌─────────────────┐
│  Traverser  │ │    LLM    │ │  Vector Store   │
│(traversal.py│ │  Layer    │ │(memory/vector_  │
│)            │ │           │ │store.py)        │
└─────────────┘ └───────────┘ └─────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                   NotionClient                              │
│                 (src/notion/client.py)                      │
│  - API wrapper with rate limiting                           │
│  - Page/block content extraction                            │
│  - Child page discovery                                     │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Notion API                                │
└─────────────────────────────────────────────────────────────┘
```

#### Index Schema (ChromaDB)

Collection: `notion_pages`
- **Document**: Searchable text (title + path + summary)
- **ID**: Notion page ID (enables direct lookup)
- **Metadata**:
  - `page_id`: Notion page ID
  - `title`: Page title
  - `path`: Breadcrumb path (e.g., "Work > Projects > 2024")
  - `summary`: LLM-generated summary
  - `content_hash`: For change detection
  - `last_edited_time`: Page last modified timestamp
  - `workspace`: Workspace name

#### Agent Tool Integration

The `NotionSearchTool` (src/tools/notion_search.py) provides:
1. **Semantic Search**: Query the vector index using natural language
2. **Direct Page Read**: Fetch full content by page ID
3. **Hybrid Mode**: Search first, then read best match

```python
# Tool parameters
{
    "query": "search query",      # Semantic search
    "page_id": "abc123",          # Direct read (bypasses search)
    "read_page": true,            # Fetch content of best match
    "max_results": 5              # Number of search results
}
```

### 5.5 Agent Preferences and Prompt Variables (`src/config/`, `src/agent/prompts.py`)
- **Purpose**: Inject dynamic variables into agent prompts and configure agent behavior
- **Key Components**:
  - `config_schema.py`: AgentConfig and AgentPreferencesConfig models
  - `prompts.py`: Template variable injection functions
- **Dependencies**: `zoneinfo` (standard library in Python 3.9+)

#### Variable Injection System

The system supports injecting runtime variables into agent system prompts:

**Supported Variables:**
- `{current_datetime}`: Current date and time in configured timezone (format: YYYY-MM-DD HH:MM:SS)
- `{timezone}`: Configured timezone (IANA timezone name)
- `{language}`: Preferred response language (ISO 639-1 code)
- `{max_history}`: Maximum number of previous messages agent can request via get_conversation_history tool
- `{tool_context}`: Context contributed by tools via the prompt injection system (see section 5.6)

**Configuration:**
```yaml
agent:
  preferences:
    timezone: "America/New_York"  # IANA timezone name
    language: "en"                 # ISO 639-1 language code
  inject_datetime: true            # Enable/disable datetime injection
  context:
    max_history: 5                 # Maximum previous messages agent can request (1-50)
```

**Template Replacement Flow:**
1. Configuration loaded and validated (timezone checked against IANA database)
2. `get_system_prompt()` called with preferences during agent initialization
3. `inject_template_variables()` replaces placeholders with actual values
4. Current datetime computed in configured timezone
5. Final prompt passed to AgentProcessor

**Backward Compatibility:**
- All agent preferences are optional with sensible defaults
- Existing prompts without placeholders continue to work
- If `agent` section omitted from config, defaults to UTC/en with datetime injection enabled

**Response Format Requirements:**
- The system prompt explicitly instructs the LLM to respond in plain natural language text
- JSON, XML, and other structured data formats are prohibited in final responses
- This prevents LLMs from outputting structured responses when tools are provided, which is common behavior in models fine-tuned for function calling

**Tool Usage Clarification:**
- The prompt explicitly states that only provided tools should be used
- LLMs are instructed not to invent or call non-existent tools (e.g., "now", "time")
- Current datetime is provided directly in the prompt, eliminating the need for a time tool
- Questions that can be answered directly should not trigger tool calls

### 5.6 Prompt Injection System (`src/agent/prompt_injection.py`)
- **Purpose**: Allow tools to contribute context to the agent's system prompt at startup
- **Key Components**:
  - `prompt_injection.py`: Base class and registry for prompt injectors
  - `src/notion/prompt_injector.py`: Notion-specific injector
- **Dependencies**: None (standard library only)

#### Prompt Injection Architecture

The prompt injection system provides a modular way for tools and integrations to add context to the agent's system prompt. This enables the agent to have awareness of available data sources without needing to call tools.

```
┌─────────────────────────────────────────────────────────────┐
│                     Startup (main.py)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              PromptInjectionRegistry                         │
│  - register(injector: BasePromptInjector)                   │
│  - collect_all_context() -> str                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
┌─────────────┐ ┌───────────┐ ┌─────────────┐
│NotionPrompt │ │Future     │ │Future       │
│Injector     │ │Calendar   │ │Injectors    │
│             │ │Injector   │ │             │
└──────┬──────┘ └───────────┘ └─────────────┘
       │
       ▼
  data/notion/info.json
```

**Base Class: `BasePromptInjector`**
- Abstract class that injectors extend
- `get_context()` -> `Optional[str]`: Returns context to inject or None
- `name`: Unique identifier for the injector
- `priority`: Order in which injectors are processed (lower = first)

**Registry: `PromptInjectionRegistry`**
- Collects and manages registered injectors
- `register(injector)`: Add an injector
- `collect_all_context()`: Gather context from all injectors, ordered by priority
- Gracefully handles injector failures (logs warning, continues)

**Notion Injector: `NotionPromptInjector`**
- Reads workspace summary from `data/notion/info.json`
- Provides context about indexed Notion pages
- Generated during Notion indexing via CLI

**info.json Schema:**
```json
{
  "generated_at": "2026-01-24T12:00:00Z",
  "summary": "Your Notion workspace contains 42 pages covering projects and notes.",
  "workspaces": [
    {
      "name": "Personal",
      "page_count": 42,
      "topics": ["Projects", "Notes", "Ideas"],
      "summary": "Contains project documentation and personal notes."
    }
  ]
}
```

**Template Variable:**
- `{tool_context}`: Placeholder in SYSTEM_PROMPT for injected context
- Replaced with combined output from all registered injectors
- Empty string if no injectors have context

**Startup Flow:**
1. `PromptInjectionRegistry` created
2. Injectors registered based on configuration (e.g., NotionPromptInjector if Notion configured)
3. `collect_all_context()` gathers context from all injectors
4. Context passed to `get_system_prompt(tool_context=...)`
5. Final prompt passed to AgentProcessor

### 6. Conversation Context (`src/context/`)
- **Purpose**: Manage conversation history and context
- **Key Components**:
  - `conversation_db.py`: SQLite database operations
  - `context_manager.py`: Context retrieval and management with smart clustering
  - `models.py`: Data models for conversations
- **Dependencies**: `aiosqlite`

#### Database Schema

**Table: messages**
- `id`: Primary key (auto-increment)
- `chat_id`: Telegram chat ID (indexed)
- `user_id`: Telegram user ID
- `message_text`: Message content
- `role`: "user" or "assistant"
- `timestamp`: ISO format UTC timestamp
- `message_id`: Telegram message ID (indexed)
- `raw_json`: Full Telegram update JSON for debugging
- `reply_to_message_id`: Telegram message ID being replied to (indexed)

**Indexes:**
- `idx_chat_id_timestamp`: Fast recent message retrieval
- `idx_message_id`: Fast message ID lookups
- `idx_chat_id`: Fast chat filtering
- `idx_reply_to_message_id`: Fast reply chain lookups

#### Contextual Conversation Chime-in

The system supports intelligent context retrieval for natural conversation engagement:

**Reply Context Injection (Story 2):**
- When a user replies to a specific message while mentioning the bot, the system automatically fetches the replied-to message
- Context is appended to the user's message for the LLM: `[Context: User is replying to a previous message: 'original text']`
- Uses `reply_to_message_id` extracted from Telegram updates

**Time-Gap Clustering (Story 1):**
- Agent can use "smart" mode to retrieve messages from the current "session"
- A session is defined by time gaps between consecutive messages
- If the gap exceeds `time_gap_threshold_minutes` (default: 60), older messages are excluded
- This filters out irrelevant old messages when user says "@bot what do you think?"

**Configuration:**
```yaml
agent:
  context:
    max_history: 5                       # Maximum messages for "recent" mode
    time_gap_threshold_minutes: 60       # Gap threshold for session detection
    lookback_limit: 25                   # Max messages to inspect for clustering
    message_limit: 20                    # Max recent messages for "llm" summarization mode
```

**Retrieval Modes:**
- `llm`: Uses LLM to generate a relevant query-based summary from recent messages. This is the only supported mode for the tool.

### 7. Memory System (`src/memory/`)
- **Purpose**: Long-term memory storage using vector database
- **Key Components**:
  - `vector_store.py`: Vector database interface (ChromaDB)
  - `embeddings.py`: Embedding generation using sentence transformers
- **Dependencies**: `chromadb`, `sentence-transformers` (optional)

### 8. Utilities (`src/utils/`)
- **Purpose**: Shared utilities
- **Key Components**:
  - `logging.py`: Logging setup with verbosity levels
- **Dependencies**: None (standard library)

### 9. Web Debug UI (`src/web/`)
- **Purpose**: Real-time visualization and debugging interface
- **Key Components**:
  - `server.py`: FastAPI server with WebSocket support
  - `registry.py`: Registry for UI subsections (modules)
  - `websocket_manager.py`: Manages real-time client connections
  - `subsections/`: Pluggable UI modules (Conversation Debugger, Config Viewer)
- **Dependencies**: `fastapi`, `uvicorn`, `websockets`

#### Web Architecture

The Web UI follows a modular, event-driven architecture using Alpine.js on the frontend and FastAPI/WebSockets on the backend.

```
┌─────────────┐      HTTP / WebSocket      ┌──────────────┐
│  Frontend   │◄──────────────────────────►│   Backend    │
│ (Alpine.js) │                            │  (FastAPI)   │
└──────┬──────┘                            └──────┬───────┘
       │                                          │
       ▼                                          ▼
┌─────────────┐                            ┌──────────────┐
│  Subsections│                            │  Subsection  │
│ Components  │                            │   Registry   │
└─────────────┘                            └──────┬───────┘
                                                  │
                                       ┌──────────┴──────────┐
                                       ▼                     ▼
                               ┌──────────────┐      ┌──────────────┐
                               │ Config Viewer│      │ Conversation │
                               │ Subsection   │      │ Debugger     │
                               └──────────────┘      └──────────────┘
```

**Key Features:**
- **Subsection Registry**: Modular UI components registered via decorators
- **Event-Driven**: Frontend components communicate via custom events (`send-action`)
- **Real-Time Updates**: WebSocket broadcasts updates from backend to subscribed frontend components
- **Alpine.js Components**: Lightweight, reactive frontend components embedded in HTML templates

## Requirements

### Functional Requirements

1. **Telegram Integration**
   - Support both polling and webhook modes
   - Validate allowed conversations and users
   - Extract and process messages
   - Send responses back to users

2. **LLM Support**
   - Support Ollama (local LLM)
   - Support OpenAI (ChatGPT)
   - Support Google Gemini
   - Unified interface for all providers

3. **Tool System**
   - Pluggable tool architecture
   - Tools receive conversation context
   - Support for Notion integration
   - Support for Google Calendar integration
   - Extensible for new tools

4. **Conversation Management**
   - Store conversation history in SQLite
   - Retrieve recent messages for context
   - Format context for LLM consumption
   - Support per-conversation state

5. **Agent Capabilities**
   - Process user commands
   - Chain multiple tool calls
   - Ask follow-up questions
   - Maintain conversation context

### Non-Functional Requirements

1. **Performance**
   - Async I/O for concurrency
   - Efficient database queries
   - Reasonable response times

2. **Reliability**
   - Error handling and recovery
   - Logging for debugging
   - Graceful degradation

3. **Security**
   - Credential management via config file
   - Input validation
   - Access control (allowed users/conversations)

4. **Maintainability**
   - Clear code structure
   - Comprehensive tests
   - Documentation

5. **Configurability**
   - YAML-based configuration
   - Environment-specific settings
   - Easy credential management

## High-Level Dependencies

### Core Dependencies
- **pydantic-ai**: AI agent framework
- **python-telegram-bot**: Telegram bot API wrapper
- **pydantic**: Data validation
- **pyyaml**: YAML parsing

### LLM Providers
- **ollama**: Local LLM client
- **openai**: OpenAI API client
- **google-genai**: Google Gemini API client

### Tool Integrations
- **notion-client**: Notion API client
- **google-api-python-client**: Google API client
- **google-auth**: Google authentication

### Storage
- **aiosqlite**: Async SQLite interface
- **chromadb**: Vector database (optional)
- **sentence-transformers**: Embedding generation (optional)

### Development
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking support

## Component Interactions

### Startup Sequence

1. Load configuration from YAML
2. Initialize conversation database
3. Initialize context manager
4. Initialize vector store (optional)
5. Create LLM instance based on config
6. Initialize Telegram client
7. Initialize tool registry with tools
8. Initialize agent processor with LLM and tools
9. Start Telegram client (poll or webhook)

### Message Processing Flow

1. Telegram message received
2. Message extractor validates chat/user IDs
3. Message extractor checks if bot is @mentioned
4. Message extractor extracts `reply_to_message_id` if present
5. Message stored in conversation database (with raw JSON and reply_to_message_id)
6. If not mentioned (and require_mention enabled), exit without responding
7. If message is a reply, fetch the replied-to message and inject context
8. Empty context created (chat_id, user_id only - NO automatic message history)
9. Agent processor processes enriched message with context metadata
10. Agent may use get_conversation_history tool with "recent" or "smart" mode
11. Agent may call other tools (with context)
12. Tools execute and return results
13. Agent generates response
14. Response sent to Telegram
15. Response stored in database

### Tool Execution Flow

1. Agent decides to call tool
2. Tool registry provides tool instance
3. Tool receives ConversationContext
4. Tool accesses conversation history, chat ID, user ID
5. Tool performs operation (API call, etc.)
6. Tool returns ToolResult
7. Agent processes result and continues

## Extension Points

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement `execute()`, `get_schema()`, `validate_input()`
3. Register in `ToolRegistry.initialize_tools()`
4. Add configuration schema if needed

### Adding New LLM Providers

1. Create LLM class inheriting from `BaseLLM`
2. Implement `generate()`, `stream_generate()`, `get_model_name()`
3. Add configuration model in `config_schema.py`
4. Add creation logic in `create_llm()` function

### Adding New Storage Backends

1. Implement storage interface
2. Update context manager to use new backend
3. Update configuration schema

## Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Mock External Services**: Mock Telegram, LLM APIs, and tool APIs
- **Test Coverage**: Aim for high coverage of core modules
- **Async Testing**: Use pytest-asyncio for async code

## Deployment Considerations

- **Single Process**: Can run as single process
- **Configuration**: Requires config.yaml with credentials
- **Dependencies**: All dependencies in requirements.txt
- **Logging**: Logs to files in logs/ directory
- **Database**: SQLite database file (can be backed up)
- **Vector DB**: ChromaDB directory (optional, can be backed up)

---

## Multi-Agent Orchestrator Architecture (Optional)

The system supports an optional multi-agent orchestrator pattern that separates routing logic from domain expertise. This pattern is disabled by default and can be enabled via configuration.

### Overview

When orchestrator mode is enabled, the system uses:
- **Dispatcher (Concierge)**: Routes requests to appropriate specialists
- **Specialist Agents**: Domain-specific agents that handle their area of expertise

### Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Dispatcher                                  │
│                        (Concierge Agent)                            │
│  - Categorizes incoming requests                                     │
│  - Delegates to appropriate specialist                               │
│  - Handles chitchat directly                                         │
│  - Never answers how-to questions                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
      ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Notion      │    │   Calendar    │    │   Memory      │
│  Specialist   │    │  Specialist   │    │  Specialist   │
│               │    │               │    │               │
│ Tools:        │    │ Tools:        │    │ Tools:        │
│ - notion_     │    │ - calendar_   │    │ - get_conv_   │
│   search      │    │   reader      │    │   history     │
│               │    │ - calendar_   │    │               │
│               │    │   writer      │    │               │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Agent-as-a-Tool Pattern

The Dispatcher uses the Agent-as-a-Tool pattern to delegate to specialists:

1. **Structured Hand-off**: Dispatcher calls specialist via Pydantic model (e.g., `NotionQuery`)
2. **Encapsulated Tools**: Specialist's internal tools are hidden from Dispatcher
3. **Context Passing**: Message history passed to specialist, but specialist's tool calls hidden from Dispatcher

```python
# Example: NotionQuery model for structured delegation (intent-focused)
class NotionQuery(BaseModel):
    user_question: str           # Full question/intent (not just keywords)
    context_hint: Optional[str]  # Additional context
    search_scope: SearchScope    # precise | exploratory | comprehensive
    time_context: Optional[str]  # Temporal hints
    max_pages_to_analyze: int    # Pages to fetch for synthesis (1-10)
```

### Notion Intelligence Engine

The NotionSpecialist includes an optional `NotionIntelligenceEngine` that provides multi-step LLM-powered search, re-ranking, and answer synthesis. When enabled, queries go through a 5-step pipeline instead of simple vector search.

#### Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Intent Analysis (LLM Call #1)                       │
│ Input: user_question, context_hint, search_scope            │
│ Output: SearchStrategy (primary_queries[], expected_type)   │
└─────────────────────────────────┬───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Execute Searches (Vector Store)                     │
│ For each query: embed → search ChromaDB → deduplicate       │
│ Output: List of raw search results                          │
└─────────────────────────────────┬───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Re-rank Results (LLM Call #2)                       │
│ Input: user_question + raw results                          │
│ Output: Ranked results with relevance scores (0-1)          │
└─────────────────────────────────┬───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Fetch Content (Notion API)                          │
│ Fetch full content for top N ranked pages                   │
└─────────────────────────────────┬───────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Synthesize Answer (LLM Call #3)                     │
│ Input: user_question + fetched page contents                │
│ Output: SynthesizedAnswer (answer, confidence, citations)   │
└─────────────────────────────────────────────────────────────┘
```

#### Internal Models

```python
# Search strategy generated by LLM
class SearchStrategy(BaseModel):
    primary_queries: List[str]      # 1-3 semantic search queries
    fallback_queries: List[str]     # Backup queries if primary returns few results
    expected_content_type: str      # What kind of content to expect
    reasoning: str                  # Why these queries were chosen

# Result with LLM-assigned relevance
class RankedResult(BaseModel):
    page_id: str
    title: str
    relevance_score: float          # 0-1 score from LLM
    relevance_reasoning: str        # Why it's relevant
    content: Optional[str]          # Full content if fetched

# Final synthesized answer
class SynthesizedAnswer(BaseModel):
    answer: str                     # Natural language answer
    confidence: float               # 0-1 confidence in answer
    citations: List[Citation]       # References to source pages
    gaps_identified: Optional[str]  # What info might be missing
    follow_up_suggestions: List[str]
```

#### Configuration

Each step of the intelligence pipeline can be toggled independently:

```yaml
agent:
  specialists:
    notion:
      intelligence:
        enabled: true              # Master switch
        query_expansion: true      # Step 1: LLM generates search queries
        llm_reranking: true        # Step 3: LLM re-ranks results
        answer_synthesis: true     # Step 5: LLM synthesizes answer
        max_queries: 3             # Max queries in expansion
        rerank_top_n: 10           # Results to consider for re-ranking
        fetch_top_n: 3             # Pages to fetch full content
```

#### Module Structure (Intelligence)

```
src/agent/specialists/
├── notion_specialist.py        # Main specialist with intelligence integration
├── notion_intelligence.py      # NotionIntelligenceEngine class
├── notion_models.py            # Pydantic models for pipeline
└── notion_prompts_internal.py  # LLM prompts for each step
```

### Data Ingestion Partitioning

Each agent sees only the data relevant to its domain:

| Agent | Data Sources |
|-------|-------------|
| **Dispatcher** | System Config + Agent Registry (agent descriptions) |
| **Notion Specialist** | info.json + ChromaDB (vector store) |
| **Calendar Specialist** | DateTime + GCal API |
| **Memory Specialist** | SQLite messages table |

### Configuration

Enable orchestrator mode in `config.yaml`:

```yaml
agent:
  orchestrator:
    enable: true  # Enable multi-agent orchestrator
    # dispatcher_model: "gpt-4"  # Optional: override LLM for dispatcher
```

### Module Structure

```
src/agent/
├── base.py              # BaseAgent, AgentContext, AgentResult
├── registry.py          # AgentRegistry for sub-agent lookup
├── dispatcher.py        # DispatcherAgent (Concierge)
├── specialists/
│   ├── base_specialist.py         # BaseSpecialistAgent
│   ├── notion_specialist.py       # NotionSpecialist
│   ├── notion_intelligence.py     # NotionIntelligenceEngine (multi-step LLM)
│   ├── notion_models.py           # Pydantic models for intelligence pipeline
│   ├── notion_prompts_internal.py # LLM prompts for intelligence steps
│   ├── calendar_specialist.py     # CalendarSpecialist
│   ├── memory_specialist.py       # MemorySpecialist
│   └── chitchat_specialist.py     # ChitchatSpecialist
└── specialist_prompts/
    ├── dispatcher_prompt.py   # Dispatcher system prompt
    ├── notion_prompt.py       # Notion specialist prompt
    ├── calendar_prompt.py     # Calendar specialist prompt
    ├── memory_prompt.py       # Memory specialist prompt
    └── chitchat_prompt.py     # Chitchat prompt

src/tools/agent_tools/
├── base_agent_tool.py     # BaseAgentTool for Agent-as-Tool pattern
├── notion_agent_tool.py   # NotionAgentTool + NotionQuery (intent-focused)
├── calendar_agent_tool.py # CalendarAgentTool + CalendarQuery
└── memory_agent_tool.py   # MemoryAgentTool + MemoryQuery
```

### Debug Features

When debugging is enabled, the system generates:

1. **Per-Response Logs**: Detailed log file for each Telegram response
2. **SVG Data Flow Diagrams**: Visual sequence diagrams showing request flow, including:
   - Tool calls with arguments and execution time
   - Independent visualization of Agent and Tool interactions
   - LLM Request/Response events with token usage (simulated)

```yaml
agent:
  debug:
    enable_response_logging: true
    enable_svg_diagrams: true
    response_log_dir: "logs/responses"
    svg_diagram_dir: "logs/diagrams"
```

Output files:
- `logs/responses/response_{chat_id}_{timestamp}.log`
- `logs/diagrams/response_{chat_id}_{timestamp}.svg`

### Debug Module Structure

```
src/debug/
├── trace.py           # TraceEvent, RequestTrace for request tracing
├── svg_generator.py   # SVGDataFlowGenerator for diagram generation
└── response_logger.py # TelegramResponseLogger for per-response logs (text + JSON + SVG)
```

**JSON Logging**: When response logging is enabled, each conversation creates two files:
- `.log` file: Human-readable text log with detailed trace events
- `.json` file: Machine-readable JSON trace for conversation debugger and future analysis

The JSON format includes full trace data, events, timing, and metadata for replay in the web UI.

### Web Debug UI (`src/web/`)

The system includes an optional browser-based debug interface with live updates via WebSockets.

#### Purpose

- Real-time monitoring of application logs
- View current configuration (read-only, with masked secrets)
- Modular architecture for adding custom debug subsections
- Live updates without page refresh

#### Module Structure

```
src/web/
├── __init__.py              # Module exports
├── server.py                # FastAPI app, WebSocket handling, WebDebugServer class
├── registry.py              # SubsectionRegistry + @subsection decorator
├── base.py                  # BaseSubsection abstract class
├── websocket_manager.py     # ConnectionManager for broadcasting updates
├── static/
│   ├── index.html           # Main page with Alpine.js
│   ├── styles.css           # Sticky header, tabs, overflow dropdown
│   └── app.js               # WebSocket client, section management
└── subsections/
    ├── __init__.py            # Auto-imports for registration
    ├── log_viewer.py          # Live log streaming subsection
    ├── config_viewer.py       # Configuration viewer subsection
    └── conversation_debugger.py # Conversation trace visualization subsection
```

#### Built-in Subsections

1. **Live Logs** (`log_viewer.py`): Real-time log streaming with filtering
2. **Configuration** (`config_viewer.py`): Read-only config viewer (masks secrets)
3. **Conversation Debugger** (`conversation_debugger.py`): Step-by-step conversation trace visualization
   - Lists all conversation traces (current and previous runs)
   - Visual data flow between components (Telegram → Dispatcher → Agents → LLM → Tools)
   - Step-by-step navigation through events
   - Real-time updates via WebSocket when new conversations occur
   - Persistent JSON storage in `logs/responses/`

#### Subsection Registration Pattern

New subsections can be added using the `@subsection` decorator:

```python
from src.web import BaseSubsection, subsection

@subsection
class MySubsection(BaseSubsection):
    def __init__(self):
        super().__init__(
            name="my-section",      # URL identifier
            display_name="My Section",  # UI display name
            priority=10,            # Lower = appears first in tab bar
            icon=""                 # Optional emoji icon
        )

    async def get_initial_data(self) -> dict:
        """Return initial data for the subsection."""
        return {"items": []}

    async def get_html_template(self) -> str:
        """Return Alpine.js-compatible HTML template."""
        return '<div x-data>Content here</div>'

    async def handle_action(self, action: str, data: dict) -> dict:
        """Handle actions from the frontend (optional)."""
        return {"success": True}
```

#### WebSocket Live Update Architecture

```
┌─────────────────┐     WebSocket      ┌─────────────────┐
│   Browser       │◄──────────────────►│  WebDebugServer │
│   (Alpine.js)   │                    │   (FastAPI)     │
└─────────────────┘                    └────────┬────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ ConnectionManager   │
                                    │ - Subscriptions     │
                                    │ - Broadcast         │
                                    └─────────────────────┘
```

**Message Types:**
- `subscribe`: Client subscribes to a subsection's updates
- `unsubscribe`: Client unsubscribes from updates
- `action`: Client sends action to subsection
- `update`: Server broadcasts data update to subscribers
- `action_result`: Server returns action result

#### Configuration

```yaml
agent:
  debug:
    enable_web_ui: true       # Enable web debug interface
    web_host: "127.0.0.1"     # Host (use 0.0.0.0 for external access)
    web_port: 8765            # Port (1024-65535)
```

#### Built-in Subsections

1. **Live Logs**: Streams application logs in real-time with level filtering
2. **Configuration**: Read-only view of current config with masked secrets

### Routing Rules

The Dispatcher routes based on message content:

| Pattern | Destination |
|---------|-------------|
| Notion/notes/documents queries | `delegate_to_notion_specialist` |
| Calendar/schedule queries | `delegate_to_calendar_specialist` |
| "What did I say..." queries | `delegate_to_memory_specialist` |
| Greetings ("hi", "thanks") | Direct response (no delegation) |

### Adding New Specialists

1. Create specialist class inheriting from `BaseSpecialistAgent`
2. Create system prompt in `specialist_prompts/`
3. Create Agent-as-Tool wrapper with Pydantic request model
4. Register in `main.py` initialization
5. Add to Dispatcher's routing rules in prompt

