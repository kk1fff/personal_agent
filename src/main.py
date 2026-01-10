"""Main entry point for Personal Agent System."""

import asyncio
import logging
import sys
from pathlib import Path

from telegram import Update

from .agent.agent_processor import AgentProcessor
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
    agent: AgentProcessor,
    context_manager: ConversationContextManager,
    message_extractor: MessageExtractor,
    telegram_client: TelegramClient,
):
    """
    Process an incoming Telegram message.

    Args:
        update: Telegram update
        agent: Agent processor
        context_manager: Conversation context manager
        message_extractor: Message extractor
        telegram_client: Telegram client
    """
    try:
        # Extract message
        extracted = message_extractor.extract(update.to_dict())
        if not extracted:
            return

        logger.info(
            f"Processing message from chat {extracted.chat_id}, user {extracted.user_id}"
        )

        # Save user message to database
        await context_manager.save_message(
            chat_id=extracted.chat_id,
            user_id=extracted.user_id,
            message=extracted.message_text,
            role="user",
            message_id=extracted.message_id,
        )

        # Get conversation context
        context = await context_manager.get_context(
            chat_id=extracted.chat_id,
            user_id=extracted.user_id,
        )

        # Process through agent
        response = await agent.process_command(extracted.message_text, context)

        # Send response back
        if response.text:
            await telegram_client.send_message(extracted.chat_id, response.text)

            # Save assistant response to database
            await context_manager.save_message(
                chat_id=extracted.chat_id,
                user_id=extracted.user_id,
                message=response.text,
                role="assistant",
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        try:
            await telegram_client.send_message(
                extracted.chat_id if extracted else 0,
                "Sorry, I encountered an error processing your message.",
            )
        except Exception:
            pass


async def main():
    """Main entry point."""
    # Load configuration (filter out verbosity flags)
    args = [arg for arg in sys.argv[1:] if arg not in ["-v", "-vv", "-vvv"]]
    config_path = args[0] if args else "config.yaml"
    logger.info(f"Loading configuration from {config_path}")

    try:
        config = load_config(config_path)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize database
    logger.info("Initializing conversation database...")
    conversation_db = ConversationDB(config.database.conversation_db)
    await conversation_db.initialize()

    # Initialize context manager
    context_manager = ConversationContextManager(conversation_db)

    # Initialize vector store (optional, for memory)
    vector_store = None
    embedding_generator = None
    try:
        vector_store = VectorStore(config.database.vector_db_path)
        embedding_generator = EmbeddingGenerator()
        logger.info("Vector store initialized")
    except ImportError:
        logger.warning(
            "Vector store dependencies not available. Memory features disabled."
        )

    # Create LLM
    logger.info(f"Initializing LLM: {config.llm.provider}")
    llm = create_llm(config)

    # Initialize Telegram client
    logger.info(f"Initializing Telegram client (mode: {config.telegram.mode})")
    telegram_client = TelegramClient(
        bot_token=config.telegram.bot_token,
        mode=config.telegram.mode,
        webhook_url=config.telegram.webhook_url,
    )

    # Initialize tool registry
    logger.info("Initializing tools...")

    async def send_message_callback(chat_id: int, text: str):
        """Callback for tools to send messages."""
        await telegram_client.send_message(chat_id, text)

    tool_registry = ToolRegistry()
    tool_registry.initialize_tools(config, send_message_callback)

    # Initialize agent processor
    logger.info("Initializing agent processor...")
    agent = AgentProcessor(
        llm=llm,
        tools=tool_registry.get_all_tools(),
    )

    # Initialize message extractor
    message_extractor = MessageExtractor(config)

    # Create message handler
    async def message_handler(update: Update):
        """Handle incoming Telegram messages."""
        await process_message(
            update,
            agent,
            context_manager,
            message_extractor,
            telegram_client,
        )

    # Start Telegram client
    logger.info("Starting Telegram bot...")
    try:
        if config.telegram.mode == "poll":
            await telegram_client.start_polling(message_handler)
        else:
            await telegram_client.start_webhook(message_handler)

        logger.info("Bot is running. Press Ctrl+C to stop.")
        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await telegram_client.stop()


if __name__ == "__main__":
    asyncio.run(main())

