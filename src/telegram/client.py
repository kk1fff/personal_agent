"""Telegram client for sending and receiving messages."""

from typing import Callable, Optional

from telegram import Bot
from telegram.error import TelegramError

from .poll_handler import PollHandler
from .webhook_handler import WebhookHandler


class TelegramClient:
    """Client for Telegram bot operations."""

    def __init__(
        self,
        bot_token: str,
        mode: str = "poll",
        webhook_url: Optional[str] = None,
        poll_interval: float = 1.0,
        webhook_port: int = 8000,
    ):
        """
        Initialize Telegram client.

        Args:
            bot_token: Telegram bot token
            mode: "poll" or "webhook"
            webhook_url: Webhook URL (required for webhook mode)
            poll_interval: Polling interval in seconds (for poll mode)
            webhook_port: Port for webhook server (for webhook mode)
        """
        self.bot_token = bot_token
        self.mode = mode
        self.webhook_url = webhook_url
        self.bot = Bot(token=bot_token)
        self.handler: Optional[PollHandler | WebhookHandler] = None
        self.poll_interval = poll_interval
        self.webhook_port = webhook_port

    async def start_polling(self, message_handler: Callable) -> None:
        """
        Start polling for messages.

        Args:
            message_handler: Async function(update: Update) -> None
        """
        if self.mode != "poll":
            raise ValueError("Client is not configured for poll mode")

        self.handler = PollHandler(
            bot_token=self.bot_token,
            message_handler=message_handler,
            poll_interval=self.poll_interval,
        )
        await self.handler.start()

    async def start_webhook(self, message_handler: Callable) -> None:
        """
        Start webhook server.

        Args:
            message_handler: Async function(update: Update) -> None
        """
        if self.mode != "webhook":
            raise ValueError("Client is not configured for webhook mode")

        if not self.webhook_url:
            raise ValueError("webhook_url is required for webhook mode")

        self.handler = WebhookHandler(
            bot_token=self.bot_token,
            webhook_url=self.webhook_url,
            message_handler=message_handler,
            port=self.webhook_port,
        )
        await self.handler.start()

    async def send_message(self, chat_id: int, text: str) -> None:
        """
        Send a message to a chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text

        Raises:
            TelegramError: If message sending fails
        """
        try:
            # Split long messages (Telegram has a 4096 character limit)
            max_length = 4096
            if len(text) <= max_length:
                await self.bot.send_message(chat_id=chat_id, text=text)
            else:
                # Split into chunks
                chunks = [
                    text[i : i + max_length] for i in range(0, len(text), max_length)
                ]
                for chunk in chunks:
                    await self.bot.send_message(chat_id=chat_id, text=chunk)
        except TelegramError as e:
            raise TelegramError(f"Failed to send message: {str(e)}")

    async def stop(self) -> None:
        """Stop the client."""
        if self.handler:
            await self.handler.stop()

