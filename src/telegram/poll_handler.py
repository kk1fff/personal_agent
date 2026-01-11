"""Poll mode handler for Telegram."""

import asyncio
import logging
from typing import Callable, Optional

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)


class PollHandler:
    """Handler for Telegram polling mode."""

    def __init__(
        self,
        bot_token: str,
        message_handler: Callable,
        poll_interval: float = 1.0,
    ):
        """
        Initialize poll handler.

        Args:
            bot_token: Telegram bot token
            message_handler: Async function(update: Update) -> None
            poll_interval: Polling interval in seconds
        """
        self.bot_token = bot_token
        self.message_handler = message_handler
        self.poll_interval = poll_interval
        self.application: Optional[Application] = None

    async def start(self) -> None:
        """Start polling for updates."""
        self.application = Application.builder().token(self.bot_token).build()

        # Add message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._handle_message)
        )

        # Start polling
        await self.application.initialize()
        await self.application.start()

        # Clear any existing webhook before polling
        logger.info("Clearing any existing webhook configuration...")
        await self.application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✓ Webhook cleared, starting polling")

        await self.application.updater.start_polling(
            poll_interval=self.poll_interval
        )

    async def stop(self) -> None:
        """Stop polling."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming message.

        Args:
            update: Telegram update
            context: Bot context
        """
        await self.message_handler(update)

