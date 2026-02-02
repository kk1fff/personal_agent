"""Per-response logging for Telegram interactions."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .trace import RequestTrace
from .svg_generator import SVGDataFlowGenerator

logger = logging.getLogger(__name__)


class TelegramResponseLogger:
    """Creates separate log files for each Telegram response.

    When debug mode is enabled, this logger creates:
    1. A detailed text log for each response
    2. An optional SVG diagram showing the agent data flow
    """

    def __init__(
        self,
        log_dir: str = "logs/responses",
        svg_dir: str = "logs/diagrams",
        enable_svg: bool = True,
        on_new_trace_callback=None,
    ):
        """Initialize response logger.

        Args:
            log_dir: Directory for response log files
            svg_dir: Directory for SVG diagram files
            enable_svg: Whether to generate SVG diagrams
            on_new_trace_callback: Optional callback to notify when a new trace is logged.
                                   Signature: async callable(trace_data: dict)
        """
        self.log_dir = Path(log_dir)
        self.svg_dir = Path(svg_dir)
        self.enable_svg = enable_svg
        self.svg_generator = SVGDataFlowGenerator()
        self.on_new_trace_callback = on_new_trace_callback

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create log directories if they don't exist."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            if self.enable_svg:
                self.svg_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create log directories: {e}")

    def log_response(
        self,
        trace: RequestTrace,
        chat_id: int,
        user_message: str,
        bot_response: str,
        user_id: Optional[int] = None,
    ) -> Optional[str]:
        """Log a complete response interaction.

        Args:
            trace: Request trace with events
            chat_id: Telegram chat ID
            user_message: User's original message
            bot_response: Bot's response
            user_id: Optional Telegram user ID

        Returns:
            Path to the log file created, or None if logging failed
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"response_{chat_id}_{timestamp}"

            # Create detailed log file
            log_path = self.log_dir / f"{filename}.log"
            self._write_log(
                log_path, trace, chat_id, user_message, bot_response, user_id
            )

            # Write JSON trace for conversation debugger
            json_path = self.log_dir / f"{filename}.json"
            self._write_json(
                json_path, trace, chat_id, user_message, bot_response, user_id
            )

            # Generate SVG diagram if enabled and there are events
            if self.enable_svg and trace.events:
                svg_path = self.svg_dir / f"{filename}.svg"
                self._write_svg(svg_path, trace)

            logger.debug(f"Response logged to {log_path}")

            # Notify callback if set
            if self.on_new_trace_callback:
                import asyncio
                trace_data = self._build_trace_data(
                    trace, chat_id, user_message, bot_response, user_id, str(json_path)
                )
                try:
                    # Schedule callback without blocking
                    asyncio.create_task(self.on_new_trace_callback(trace_data))
                except Exception as e:
                    logger.warning(f"Failed to invoke trace callback: {e}")

            return str(log_path)

        except Exception as e:
            logger.error(f"Failed to log response: {e}", exc_info=True)
            return None

    def _write_log(
        self,
        path: Path,
        trace: RequestTrace,
        chat_id: int,
        user_message: str,
        bot_response: str,
        user_id: Optional[int] = None,
    ) -> None:
        """Write detailed log file.

        Args:
            path: Path to write log file
            trace: Request trace
            chat_id: Telegram chat ID
            user_message: User's message
            bot_response: Bot's response
            user_id: Optional user ID
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("TELEGRAM RESPONSE LOG\n")
            f.write("=" * 70 + "\n\n")

            # Trace metadata
            f.write(f"Trace ID: {trace.trace_id}\n")
            f.write(f"Chat ID: {chat_id}\n")
            if user_id:
                f.write(f"User ID: {user_id}\n")
            f.write(f"Timestamp: {trace.start_time.isoformat()}\n")

            if trace.end_time:
                duration = trace.get_duration_ms()
                f.write(f"Duration: {duration:.2f}ms\n")

            f.write("\n" + "-" * 70 + "\n")
            f.write("USER MESSAGE:\n")
            f.write("-" * 70 + "\n")
            f.write(user_message + "\n")

            f.write("\n" + "-" * 70 + "\n")
            f.write("BOT RESPONSE:\n")
            f.write("-" * 70 + "\n")
            f.write(bot_response + "\n")

            f.write("\n" + "-" * 70 + "\n")
            f.write(f"TRACE EVENTS ({len(trace.events)}):\n")
            f.write("-" * 70 + "\n\n")

            for i, event in enumerate(trace.events, 1):
                time_offset = (event.timestamp - trace.start_time).total_seconds() * 1000
                f.write(f"[{i}] +{time_offset:.1f}ms\n")
                f.write(f"    Type: {event.event_type.value}\n")
                f.write(f"    {event.source} -> {event.target}\n")
                f.write(f"    {event.content_summary}\n")
                if event.duration_ms:
                    f.write(f"    Duration: {event.duration_ms:.2f}ms\n")
                
                # Print metadata if available
                if event.metadata:
                    f.write("    Metadata:\n")
                    for key, value in event.metadata.items():
                        # Handle long values (like full LLM content)
                        val_str = str(value)
                        if "\n" in val_str or len(val_str) > 100:
                            f.write(f"      {key}:\n")
                            for line in val_str.split("\n"):
                                f.write(f"        {line}\n")
                        else:
                            f.write(f"      {key}: {value}\n")
                f.write("\n")

            f.write("=" * 70 + "\n")
            f.write("END OF LOG\n")
            f.write("=" * 70 + "\n")

    def _write_json(
        self,
        path: Path,
        trace: RequestTrace,
        chat_id: int,
        user_message: str,
        bot_response: str,
        user_id: Optional[int] = None,
    ) -> None:
        """Write JSON trace file for conversation debugger.

        Args:
            path: Path to write JSON file
            trace: Request trace
            chat_id: Telegram chat ID
            user_message: User's message
            bot_response: Bot's response
            user_id: Optional user ID
        """
        import json
        
        data = self._build_trace_data(
            trace, chat_id, user_message, bot_response, user_id, str(path)
        )
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _build_trace_data(
        self,
        trace: RequestTrace,
        chat_id: int,
        user_message: str,
        bot_response: str,
        user_id: Optional[int] = None,
        file_path: str = "",
    ) -> dict:
        """Build trace data dictionary for JSON and callbacks.

        Args:
            trace: Request trace
            chat_id: Telegram chat ID
            user_message: User's message
            bot_response: Bot's response
            user_id: Optional user ID
            file_path: Path to JSON file

        Returns:
            Dictionary with trace data
        """
        return {
            "trace_id": trace.trace_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "timestamp": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "duration_ms": trace.get_duration_ms(),
            "user_message": user_message,
            "bot_response": bot_response,
            "file_path": file_path,
            "events": [e.to_dict() for e in trace.events],
        }


    def _write_svg(self, path: Path, trace: RequestTrace) -> None:
        """Generate and write SVG diagram.

        Args:
            path: Path to write SVG file
            trace: Request trace to visualize
        """
        try:
            svg_content = self.svg_generator.generate(trace.to_svg_data())
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            logger.debug(f"SVG diagram written to {path}")
        except Exception as e:
            logger.warning(f"Failed to generate SVG diagram: {e}")

    def cleanup_old_logs(self, max_age_days: int = 7) -> int:
        """Remove log files older than specified age.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of files removed
        """
        removed = 0
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)

        for directory in [self.log_dir, self.svg_dir]:
            if not directory.exists():
                continue

            for file in directory.iterdir():
                if file.is_file():
                    try:
                        if file.stat().st_mtime < cutoff:
                            file.unlink()
                            removed += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove {file}: {e}")

        if removed > 0:
            logger.info(f"Cleaned up {removed} old log files")

        return removed
