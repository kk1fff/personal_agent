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
  - `notion_reader.py`: Notion page reading tool
  - `notion_writer.py`: Notion page writing tool
  - `calendar_reader.py`: Google Calendar reading tool
  - `calendar_writer.py`: Google Calendar writing tool
  - `registry.py`: Centralized tool registry
- **Dependencies**: `notion-client`, `google-api-python-client`, `google-auth`

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

