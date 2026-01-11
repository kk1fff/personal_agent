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
3. **Storage**: Valid messages are stored in SQLite conversation database
4. **Context Retrieval**: Recent conversation history is retrieved for context
5. **Agent Processing**: Agent processes message with LLM and available tools
6. **Tool Execution**: Tools execute with conversation context when needed
7. **Response**: Agent response is sent back to Telegram and stored

## Constraints

- **Python 3.8+**: Minimum Python version requirement
- **Async/Await**: All I/O operations use async/await for concurrency
- **Configuration-Driven**: System behavior controlled via YAML configuration
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
  - `config_schema.py`: Pydantic models for configuration validation
- **Dependencies**: `pyyaml`, `pydantic`

### 2. Telegram Integration (`src/telegram/`)
- **Purpose**: Handle Telegram bot communication
- **Key Components**:
  - `client.py`: Main Telegram client wrapper
  - `poll_handler.py`: Polling mode handler
  - `webhook_handler.py`: Webhook mode handler
  - `message_extractor.py`: Message extraction and validation
- **Dependencies**: `python-telegram-bot`

### 3. Agent Processor (`src/agent/`)
- **Purpose**: Core AI agent orchestration
- **Key Components**:
  - `agent_processor.py`: Main agent processing logic using pydantic_ai
  - `prompts.py`: Centralized system prompts
- **Dependencies**: `pydantic-ai`

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
  - `chat_reply.py`: Telegram message sending tool
  - `notion_reader.py`: Notion page reading tool
  - `notion_writer.py`: Notion page writing tool
  - `calendar_reader.py`: Google Calendar reading tool
  - `calendar_writer.py`: Google Calendar writing tool
  - `registry.py`: Centralized tool registry
- **Dependencies**: `notion-client`, `google-api-python-client`, `google-auth`

### 6. Conversation Context (`src/context/`)
- **Purpose**: Manage conversation history and context
- **Key Components**:
  - `conversation_db.py`: SQLite database operations
  - `context_manager.py`: Context retrieval and management
  - `models.py`: Data models for conversations
- **Dependencies**: `aiosqlite`

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
3. Message stored in conversation database
4. Context manager retrieves recent messages
5. Agent processor processes message with context
6. Agent may call tools (with context)
7. Tools execute and return results
8. Agent generates response
9. Response sent to Telegram
10. Response stored in database

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

