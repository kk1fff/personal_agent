"""Main entry point for Personal Agent System."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Union

from telegram import Update

from .agent.agent_processor import AgentProcessor
from .agent.prompt_injection import PromptInjectionRegistry
from .agent.prompts import get_system_prompt
from .notion.prompt_injector import NotionPromptInjector
from .config.config_loader import load_config
from .context.conversation_db import ConversationDB
from .context.context_manager import ConversationContextManager
from .llm.gemini_llm import GeminiLLM
from .llm.ollama_llm import OllamaLLM
from .llm.openai_llm import OpenAILLM
from .memory.embeddings import EmbeddingGenerator
from .memory.vector_store import VectorStore
from .telegram.client import TelegramClient
from .telegram.message_extractor import MessageExtractor
from .tools.registry import ToolRegistry
from .utils.logging import parse_verbosity, setup_logging

# Multi-agent orchestrator imports
from .agent.base import AgentContext, AgentResult
from .agent.registry import AgentRegistry
from .agent.dispatcher import DispatcherAgent
from .agent.specialists import (
    NotionSpecialist,
    CalendarSpecialist,
    MemorySpecialist,
    ChitchatSpecialist,
)
from .tools.agent_tools import (
    NotionAgentTool,
    CalendarAgentTool,
    MemoryAgentTool,
)
from .debug import RequestTrace, TraceEventType, TelegramResponseLogger

# Set up logging with verbosity support
verbosity = parse_verbosity(sys.argv)
logger = setup_logging(verbosity=verbosity)


def create_llm(config):
    """
    Create LLM instance based on configuration.

    Args:
        config: Application configuration

    Returns:
        BaseLLM instance
    """
    provider = config.llm.provider.lower()

    if provider == "ollama":
        if not config.llm.ollama:
            raise ValueError("Ollama configuration is required")
        return OllamaLLM(
            model=config.llm.ollama.model,
            base_url=config.llm.ollama.base_url,
            temperature=config.llm.ollama.temperature,
            max_tokens=config.llm.ollama.max_tokens,
            context_window=config.llm.ollama.context_window,
        )

    elif provider == "openai":
        if not config.llm.openai:
            raise ValueError("OpenAI configuration is required")
        return OpenAILLM(
            api_key=config.llm.openai.api_key,
            model=config.llm.openai.model,
            temperature=config.llm.openai.temperature,
            max_tokens=config.llm.openai.max_tokens,
            organization_id=config.llm.openai.organization_id,
        )

    elif provider == "gemini":
        if not config.llm.gemini:
            raise ValueError("Gemini configuration is required")
        return GeminiLLM(
            api_key=config.llm.gemini.api_key,
            model=config.llm.gemini.model,
            temperature=config.llm.gemini.temperature,
            max_tokens=config.llm.gemini.max_tokens,
            safety_settings=config.llm.gemini.safety_settings,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def process_message(
    update: Update,
    agent: Union[AgentProcessor, DispatcherAgent],
    context_manager: ConversationContextManager,
    message_extractor: MessageExtractor,
    telegram_client: TelegramClient,
    response_logger: Optional[TelegramResponseLogger] = None,
    timezone: str = "UTC",
):
    """
    Process an incoming Telegram message.

    Args:
        update: Telegram update
        agent: Agent processor (legacy) or Dispatcher agent (orchestrator)
        context_manager: Conversation context manager
        message_extractor: Message extractor
        telegram_client: Telegram client
        response_logger: Optional per-response logger for debug mode
        timezone: Timezone for agent context
    """
    extracted = None
    trace = None

    try:
        # Extract message
        extracted = message_extractor.extract(update.to_dict())
        if not extracted:
            return

        logger.info(
            f"Processing message from chat {extracted.chat_id}, user {extracted.user_id}"
        )

        # ALWAYS save user message to database (even if not mentioned)
        await context_manager.save_message(
            chat_id=extracted.chat_id,
            user_id=extracted.user_id,
            message=extracted.message_text,
            role="user",
            message_id=extracted.message_id,
            raw_json=extracted.raw_json,
            reply_to_message_id=extracted.reply_to_message_id,
        )

        # Check if bot was mentioned before responding
        if not extracted.is_mentioned:
            logger.debug(
                f"Message from chat {extracted.chat_id} does not mention bot, "
                "message saved but not responding"
            )
            return  # Exit without responding

        # Only process and respond if mentioned
        logger.info("Bot mentioned, processing with agent...")

        # Create request trace for debugging
        if response_logger:
            trace = RequestTrace()
            trace.add_event(
                TraceEventType.REQUEST,
                source="telegram",
                target="dispatcher" if isinstance(agent, DispatcherAgent) else "agent",
                content_summary=extracted.message_text[:100],
            )

        # Build message with reply context if applicable (Story 2: Reply Tagging)
        user_message = extracted.message_text
        if extracted.reply_to_message_id:
            replied_msg = await context_manager.get_message_by_id(
                extracted.chat_id,
                extracted.reply_to_message_id,
            )
            if replied_msg:
                user_message = (
                    f"{extracted.message_text}\n\n"
                    f"[Context: User is replying to a previous message: "
                    f"'{replied_msg.message_text}']"
                )
                logger.debug(
                    f"Added reply context from message {extracted.reply_to_message_id}"
                )

        # Process based on agent type
        if isinstance(agent, DispatcherAgent):
            # Orchestrator mode: use AgentContext
            agent_context = AgentContext(
                chat_id=extracted.chat_id,
                user_id=extracted.user_id,
                session_id=f"{extracted.chat_id}_{extracted.user_id}",
                message_history=[],
                metadata={
                    "timezone": timezone,
                    "trace": trace,
                },
            )

            result = await agent.process(user_message, agent_context)
            response_text = result.response_text

            if trace:
                trace.add_event(
                    TraceEventType.RESPONSE,
                    source="dispatcher",
                    target="telegram",
                    content_summary=response_text[:100] if response_text else "",
                    duration_ms=result.processing_time_ms,
                )
        else:
            # Legacy mode: use ConversationContext
            from .context.models import ConversationContext
            context = ConversationContext(
                chat_id=extracted.chat_id,
                user_id=extracted.user_id,
                messages=[],  # Empty - agent must request history via tool
            )

            response = await agent.process_command(user_message, context)
            response_text = response.text

            if trace:
                trace.add_event(
                    TraceEventType.RESPONSE,
                    source="agent",
                    target="telegram",
                    content_summary=response_text[:100] if response_text else "",
                )

        # Send response back
        if response_text:
            await telegram_client.send_message(extracted.chat_id, response_text)

            # Save assistant response to database
            await context_manager.save_message(
                chat_id=extracted.chat_id,
                user_id=extracted.user_id,
                message=response_text,
                role="assistant",
                raw_json=None,
            )

        # Log response if debug enabled
        if response_logger and trace:
            trace.complete()
            response_logger.log_response(
                trace=trace,
                chat_id=extracted.chat_id,
                user_message=user_message,
                bot_response=response_text or "",
                user_id=extracted.user_id,
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

        if trace:
            trace.add_event(
                TraceEventType.ERROR,
                source="system",
                target="error",
                content_summary=str(e),
            )

        try:
            await telegram_client.send_message(
                extracted.chat_id if extracted else 0,
                "Sorry, I encountered an error processing your message.",
            )
        except Exception:
            pass


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Personal Agent System - Starting")
    logger.info("=" * 60)

    # Load configuration (filter out verbosity flags)
    args = [arg for arg in sys.argv[1:] if arg not in ["-v", "-vv", "-vvv"]]
    config_path = args[0] if args else "config.yaml"
    logger.info(f"[1/7] Loading configuration from: {config_path}")

    try:
        config = load_config(config_path)
        logger.info(f"✓ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize database
    logger.info(f"[2/7] Initializing conversation database")
    logger.info(f"  Database path: {config.database.conversation_db}")
    conversation_db = ConversationDB(config.database.conversation_db)
    await conversation_db.initialize()
    logger.info("✓ Conversation database ready")


    # Initialize vector store (optional, for memory)
    vector_store = None
    embedding_generator = None
    logger.info(f"[3/7] Initializing vector store")
    logger.info(f"  Vector DB path: {config.database.vector_db_path}")
    try:
        vector_store = VectorStore(config.database.vector_db_path)
        embedding_generator = EmbeddingGenerator()
        logger.info("✓ Vector store ready - Memory features enabled")
    except ImportError as e:
        logger.warning(
            f"✗ Vector store dependencies not available: {e}"
        )
        logger.warning("  Memory features disabled")

    # Create LLM
    logger.info(f"[4/7] Initializing LLM")
    logger.info(f"  Provider: {config.llm.provider}")

    # Log provider-specific details
    if config.llm.provider.lower() == "ollama":
        logger.info(f"  Model: {config.llm.ollama.model}")
        logger.info(f"  Base URL: {config.llm.ollama.base_url}")
        logger.info(f"  Temperature: {config.llm.ollama.temperature}")
        logger.info(f"  Max tokens: {config.llm.ollama.max_tokens}")
        if config.llm.ollama.context_window:
            logger.info(f"  Context window: {config.llm.ollama.context_window}")
    elif config.llm.provider.lower() == "openai":
        logger.info(f"  Model: {config.llm.openai.model}")
        logger.info(f"  Temperature: {config.llm.openai.temperature}")
        logger.info(f"  Max tokens: {config.llm.openai.max_tokens}")
    elif config.llm.provider.lower() == "gemini":
        logger.info(f"  Model: {config.llm.gemini.model}")
        logger.info(f"  Temperature: {config.llm.gemini.temperature}")
        logger.info(f"  Max tokens: {config.llm.gemini.max_tokens}")

    llm = create_llm(config)
    logger.info(f"✓ LLM initialized: {llm.get_model_name()}")

    # Validate LLM is working
    logger.info("  Validating LLM connection...")
    try:
        await llm.validate()
    except Exception as e:
        logger.error(f"✗ LLM validation failed: {e}")
        logger.error("  Please check that:")

        if config.llm.provider.lower() == "ollama":
            logger.error(f"    - Ollama is running at {config.llm.ollama.base_url}")
            logger.error(f"    - Model '{config.llm.ollama.model}' is installed")
            logger.error(f"  Run: ollama list (to see installed models)")
            logger.error(f"  Run: ollama pull {config.llm.ollama.model} (to install the model)")
        elif config.llm.provider.lower() == "openai":
            logger.error(f"    - API key is valid")
            logger.error(f"    - Model '{config.llm.openai.model}' is accessible")
        elif config.llm.provider.lower() == "gemini":
            logger.error(f"    - API key is valid")
            logger.error(f"    - Model '{config.llm.gemini.model}' is accessible")

        sys.exit(1)

    # Initialize context manager with config settings
    logger.info("[5/7] Initializing context manager")
    context_config = config.agent.context
    context_manager = ConversationContextManager(
        conversation_db,
        default_limit=context_config.max_history,
        time_gap_threshold_minutes=context_config.time_gap_threshold_minutes,
        lookback_limit=context_config.lookback_limit,
        llm=llm,
        message_limit=context_config.message_limit,
    )
    logger.info("✓ Context manager ready")
    logger.info(f"  Time gap threshold: {context_config.time_gap_threshold_minutes} min")
    logger.info(f"  Lookback limit: {context_config.lookback_limit} messages")
    logger.info(f"  Message limit (LLM): {context_config.message_limit} messages")

    # Initialize Telegram client
    logger.info(f"[6/7] Initializing Telegram client")
    logger.info(f"  Mode: {config.telegram.mode}")
    if config.telegram.mode == "webhook":
        logger.info(f"  Webhook URL: {config.telegram.webhook_url}")
    telegram_client = TelegramClient(
        bot_token=config.telegram.bot_token,
        mode=config.telegram.mode,
        webhook_url=config.telegram.webhook_url,
    )
    logger.info("✓ Telegram client ready")

    # Initialize tool registry
    logger.info("[7/7] Initializing tools")

    tool_registry = ToolRegistry()
    tool_registry.initialize_tools(config, context_manager)

    # Log registered tools
    registered_tools = tool_registry.get_all_tools()
    logger.info(f"  Registered tools ({len(registered_tools)}):")
    for tool in registered_tools:
        logger.info(f"    - {tool.get_name()}: {tool.get_description()}")
    logger.info("✓ Tools ready")

    # Initialize message extractor
    logger.info("Initializing message extractor")
    message_extractor = MessageExtractor(config)
    logger.info("✓ Message extractor ready")

    # Auto-detect or use configured bot username
    bot_username = None
    if config.telegram.require_mention or config.telegram.bot_username:
        bot_username = config.telegram.bot_username

        if not bot_username:
            logger.info("Auto-detecting bot username from Telegram API...")
            try:
                bot_info = await telegram_client.bot.get_me()
                bot_username = bot_info.username
                logger.info(f"✓ Bot username detected: @{bot_username}")
            except Exception as e:
                logger.error(f"✗ Failed to auto-detect bot username: {e}")
                if config.telegram.require_mention:
                    logger.error("  Set bot_username in config.yaml or disable require_mention")
                    sys.exit(1)
                else:
                    logger.warning("  Continuing without bot username in system prompt")
                    bot_username = None
        else:
            logger.info(f"Using configured bot username: @{bot_username}")

        if bot_username and config.telegram.require_mention:
            message_extractor.set_bot_username(bot_username)
            logger.info(f"✓ @Mention filtering enabled for @{bot_username}")

    if not config.telegram.require_mention:
        logger.info("@Mention filtering disabled - responding to all allowed messages")

    # Initialize prompt injection registry
    logger.info("Initializing prompt injectors")
    injection_registry = PromptInjectionRegistry()

    # Register Notion injector if Notion is configured
    if config.tools.notion and config.tools.notion.api_key:
        notion_injector = NotionPromptInjector()
        injection_registry.register(notion_injector)
        logger.info("  Registered: Notion prompt injector")

    # Collect tool context from all injectors
    tool_context = injection_registry.collect_all_context()
    if tool_context:
        logger.info("  Tool context collected successfully")
        logger.debug(f"  Tool context preview: {tool_context[:200]}...")
    else:
        logger.info("  No tool context available (run indexers to generate)")

    # Initialize debug response logger if enabled
    response_logger = None
    debug_config = config.agent.debug
    if debug_config.enable_response_logging:
        logger.info("Initializing debug response logger")
        response_logger = TelegramResponseLogger(
            log_dir=debug_config.response_log_dir,
            svg_dir=debug_config.svg_diagram_dir,
            enable_svg=debug_config.enable_svg_diagrams,
        )
        logger.info("✓ Debug response logger ready")
        logger.info(f"  Response logs: {debug_config.response_log_dir}")
        if debug_config.enable_svg_diagrams:
            logger.info(f"  SVG diagrams: {debug_config.svg_diagram_dir}")

    # Initialize agent (orchestrator or legacy mode)
    agent_config = config.agent
    orchestrator_config = agent_config.orchestrator

    if orchestrator_config.enable:
        # Multi-agent orchestrator mode
        logger.info("Initializing multi-agent orchestrator")
        logger.info("  Mode: Orchestrator (Dispatcher + Specialists)")

        # Create agent registry
        agent_registry = AgentRegistry()

        # Get tools by name for specialists
        all_tools = {t.get_name(): t for t in tool_registry.get_all_tools()}

        # Create specialists with their specific tools
        specialists = []

        # Notion Specialist
        if "notion_search" in all_tools:
            notion_specialist = NotionSpecialist(
                llm=llm,
                notion_search_tool=all_tools["notion_search"],
                notion_context=tool_context,
            )
            agent_registry.register(notion_specialist)
            specialists.append(notion_specialist)
            logger.info("    - Notion Specialist registered")

        # Calendar Specialist
        calendar_reader = all_tools.get("calendar_reader")
        calendar_writer = all_tools.get("calendar_writer")
        if calendar_reader or calendar_writer:
            calendar_specialist = CalendarSpecialist(
                llm=llm,
                calendar_reader_tool=calendar_reader,
                calendar_writer_tool=calendar_writer,
            )
            agent_registry.register(calendar_specialist)
            specialists.append(calendar_specialist)
            logger.info("    - Calendar Specialist registered")

        # Memory Specialist
        if "get_conversation_history" in all_tools:
            memory_specialist = MemorySpecialist(
                llm=llm,
                context_manager_tool=all_tools["get_conversation_history"],
            )
            agent_registry.register(memory_specialist)
            specialists.append(memory_specialist)
            logger.info("    - Memory Specialist registered")

        # Chitchat Specialist (always available)
        chitchat_specialist = ChitchatSpecialist(llm=llm)
        agent_registry.register(chitchat_specialist)
        specialists.append(chitchat_specialist)
        logger.info("    - Chitchat Specialist registered")

        # Create agent-as-tool wrappers
        agent_tools = []
        for specialist in specialists:
            if isinstance(specialist, NotionSpecialist):
                agent_tools.append(NotionAgentTool(specialist))
            elif isinstance(specialist, CalendarSpecialist):
                agent_tools.append(CalendarAgentTool(specialist))
            elif isinstance(specialist, MemorySpecialist):
                agent_tools.append(MemoryAgentTool(specialist))
            # Note: Chitchat is handled directly by dispatcher, no tool wrapper needed

        # Create dispatcher
        agent = DispatcherAgent(
            llm=llm,
            agent_registry=agent_registry,
            agent_tools=agent_tools,
            timezone=agent_config.preferences.timezone,
        )
        logger.info("✓ Dispatcher agent ready")
        logger.info(f"  Specialists: {len(specialists)}")
        logger.info(f"  Agent tools: {len(agent_tools)}")

    else:
        # Legacy single-agent mode
        logger.info("Initializing agent processor (legacy mode)")
        system_prompt = get_system_prompt(
            bot_username=bot_username,
            timezone=agent_config.preferences.timezone,
            language=agent_config.preferences.language,
            inject_datetime=agent_config.inject_datetime,
            max_history=agent_config.context.max_history,
            tool_context=tool_context,
        )
        agent = AgentProcessor(
            llm=llm,
            tools=tool_registry.get_all_tools(),
            system_prompt=system_prompt,
        )
        logger.info("✓ Agent processor ready")

    if bot_username:
        logger.info(f"  Bot identifies as: @{bot_username}")
    logger.info(f"  Timezone: {agent_config.preferences.timezone}")
    logger.info(f"  Language: {agent_config.preferences.language}")
    logger.info(f"  Datetime injection: {'enabled' if agent_config.inject_datetime else 'disabled'}")

    # Create message handler
    async def message_handler(update: Update):
        """Handle incoming Telegram messages."""
        await process_message(
            update,
            agent,
            context_manager,
            message_extractor,
            telegram_client,
            response_logger=response_logger,
            timezone=agent_config.preferences.timezone,
        )

    # Start Telegram client
    logger.info("=" * 60)
    logger.info("Starting Telegram bot")
    logger.info("=" * 60)
    try:
        if config.telegram.mode == "poll":
            logger.info("Starting polling mode...")
            await telegram_client.start_polling(message_handler)
        else:
            logger.info("Starting webhook mode...")
            await telegram_client.start_webhook(message_handler)

        logger.info("=" * 60)
        logger.info("✓ SYSTEM READY - Bot is now listening for messages")
        logger.info("=" * 60)
        logger.info(f"  LLM: {llm.get_model_name()}")
        logger.info(f"  Telegram Mode: {config.telegram.mode}")
        logger.info(f"  Agent Mode: {'Orchestrator' if orchestrator_config.enable else 'Legacy'}")
        logger.info(f"  Tools: {len(registered_tools)} registered")
        if response_logger:
            logger.info("  Debug Logging: Enabled")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Shutdown initiated")
        logger.info("=" * 60)
    finally:
        logger.info("Stopping Telegram client...")
        await telegram_client.stop()
        logger.info("✓ Telegram client stopped")
        logger.info("=" * 60)
        logger.info("✓ Personal Agent System shutdown complete")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

