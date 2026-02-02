"""WebSocket connection manager for live updates."""

from typing import Dict, List, Set, Any
import logging
import json

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""

    def __init__(self):
        # All active connections
        self._connections: Set[WebSocket] = set()
        # Subscription mapping: subsection_name -> set of websockets
        self._subscriptions: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.debug(f"WebSocket connected. Total connections: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self._connections.discard(websocket)
        # Remove from all subscriptions
        for subscribers in self._subscriptions.values():
            subscribers.discard(websocket)
        logger.debug(
            f"WebSocket disconnected. Total connections: {len(self._connections)}"
        )

    async def subscribe(self, websocket: WebSocket, subsection_name: str) -> None:
        """Subscribe a connection to a subsection's updates."""
        if subsection_name not in self._subscriptions:
            self._subscriptions[subsection_name] = set()
        self._subscriptions[subsection_name].add(websocket)
        logger.debug(f"WebSocket subscribed to {subsection_name}")

    def unsubscribe(self, websocket: WebSocket, subsection_name: str) -> None:
        """Unsubscribe a connection from a subsection."""
        if subsection_name in self._subscriptions:
            self._subscriptions[subsection_name].discard(websocket)

    async def broadcast_to_subsection(
        self, subsection_name: str, data: Dict[str, Any]
    ) -> None:
        """Broadcast a message to all subscribers of a subsection."""
        if subsection_name not in self._subscriptions:
            return

        subscribers = self._subscriptions[subsection_name].copy()
        disconnected = []

        for websocket in subscribers:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(f"Failed to send to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_all(self, data: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected = []

        for websocket in self._connections.copy():
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(f"Failed to send to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws)

    async def disconnect_all(self) -> None:
        """Disconnect all clients gracefully."""
        for websocket in self._connections.copy():
            try:
                await websocket.close()
            except Exception:
                pass
        self._connections.clear()
        self._subscriptions.clear()

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)
