"""Webhook mode handler for Telegram."""

from typing import Callable, Optional

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters


class WebhookHandler:
    """Handler for Telegram webhook mode."""

    def __init__(
        self,
        bot_token: str,
        webhook_url: str,
        message_handler: Callable,
        port: int = 8000,
    ):
        """
        Initialize webhook handler.

        Args:
            bot_token: Telegram bot token
            webhook_url: Public URL for webhook
            message_handler: Async function(update: Update) -> None
            port: Local port to listen on
        """
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.message_handler = message_handler
        self.port = port
        self.application: Optional[Application] = None

    async def start(self) -> None:
        """Start webhook server."""
        self.application = Application.builder().token(self.bot_token).build()

        # Add message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._handle_message)
        )

        # Initialize and start application
        await self.application.initialize()
        await self.application.start()

        # Set up webhook using python-telegram-bot's built-in webhook support
        await self.application.bot.set_webhook(url=self.webhook_url)

        # Start webhook server using python-telegram-bot's webhook server
        await self.application.updater.start_webhook(
            listen="0.0.0.0",
            port=self.port,
            webhook_url=self.webhook_url,
        )

    async def stop(self) -> None:
        """Stop webhook server."""
        if self.application:
            await self.application.updater.stop()
            await self.application.bot.delete_webhook()
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

