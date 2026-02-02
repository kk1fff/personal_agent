"""Live log viewer subsection."""

import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import BaseSubsection
from ..registry import subsection


class WebLogHandler(logging.Handler):
    """Custom logging handler that stores logs for the web UI."""

    def __init__(self, max_entries: int = 500):
        super().__init__()
        self.logs: deque = deque(maxlen=max_entries)
        self._broadcast_callback: Optional[callable] = None

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                )[:-3],
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            self.logs.append(log_entry)

            # Broadcast to websocket if callback is set
            if self._broadcast_callback:
                try:
                    import asyncio

                    asyncio.create_task(
                        self._broadcast_callback({"new_log": log_entry})
                    )
                except RuntimeError:
                    # No event loop running, skip broadcast
                    pass
        except Exception:
            self.handleError(record)

    def set_broadcast_callback(self, callback: callable) -> None:
        """Set the callback function for broadcasting new logs."""
        self._broadcast_callback = callback

    def get_logs(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get stored logs, optionally filtered by level."""
        logs = list(self.logs)
        if level and level != "ALL":
            level_order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            min_level = level_order.get(level, 0)
            logs = [log for log in logs if level_order.get(log["level"], 0) >= min_level]
        return logs


# Global handler instance
_log_handler: Optional[WebLogHandler] = None


def get_log_handler() -> WebLogHandler:
    """Get or create the global log handler."""
    global _log_handler
    if _log_handler is None:
        _log_handler = WebLogHandler()
        _log_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        # Attach to root logger
        logging.getLogger().addHandler(_log_handler)
    return _log_handler


@subsection
class LogViewerSubsection(BaseSubsection):
    """Live log streaming subsection."""

    def __init__(self):
        super().__init__(
            name="logs",
            display_name="Live Logs",
            priority=10,
            icon="",
        )
        self._handler = get_log_handler()

    async def get_initial_data(self) -> Dict[str, Any]:
        """Get initial log data."""
        return {
            "logs": self._handler.get_logs(),
            "levels": ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "selectedLevel": "ALL",
            "autoScroll": True,
        }

    async def get_html_template(self) -> str:
        """Get HTML template for log viewer."""
        return '''
<div class="log-viewer" x-data="{
    filteredLogs: data.logs,
    selectedLevel: data.selectedLevel,
    autoScroll: data.autoScroll,
    filterLogs() {
        const levelOrder = {DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50};
        if (this.selectedLevel === 'ALL') {
            this.filteredLogs = data.logs;
        } else {
            const minLevel = levelOrder[this.selectedLevel] || 0;
            this.filteredLogs = data.logs.filter(log => (levelOrder[log.level] || 0) >= minLevel);
        }
    },
    scrollToBottom() {
        if (this.autoScroll) {
            this.$nextTick(() => {
                const container = this.$refs.logContainer;
                if (container) container.scrollTop = container.scrollHeight;
            });
        }
    }
}" x-init="$watch('data.logs', () => { filterLogs(); scrollToBottom(); }); filterLogs();">
    <div class="log-controls">
        <label>
            Level:
            <select x-model="selectedLevel" @change="filterLogs()">
                <template x-for="level in data.levels" :key="level">
                    <option :value="level" x-text="level"></option>
                </template>
            </select>
        </label>
        <label>
            <input type="checkbox" x-model="autoScroll">
            Auto-scroll
        </label>
        <button @click="sendAction('clear')">Clear</button>
        <span style="color: #6b7280; font-size: 12px;" x-text="'(' + filteredLogs.length + ' entries)'"></span>
    </div>
    <div class="log-entries" x-ref="logContainer">
        <template x-for="(log, index) in filteredLogs" :key="index">
            <div class="log-entry" :class="log.level">
                <span class="log-timestamp" x-text="log.timestamp"></span>
                <span class="log-level" x-text="log.level"></span>
                <span class="log-message" x-text="log.message"></span>
            </div>
        </template>
        <div x-show="filteredLogs.length === 0" style="color: #6b7280; padding: 20px; text-align: center;">
            No log entries
        </div>
    </div>
</div>
'''

    async def handle_action(
        self, action: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle actions from the frontend."""
        if action == "clear":
            self._handler.logs.clear()
            return {"success": True, "logs": []}
        return await super().handle_action(action, data)

    def set_broadcast_callback(self, callback: callable) -> None:
        """Set up broadcasting for new log entries."""
        self._handler.set_broadcast_callback(callback)
