"""FastAPI web server for debug UI."""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .registry import SubsectionRegistry
from .websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)


class WebDebugServer:
    """Web server for debug UI with live updates."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        registry: Optional[SubsectionRegistry] = None,
    ):
        self.host = host
        self.port = port
        self.registry = registry
        self.app = FastAPI(title="Personal Agent Debug UI")
        self.manager = ConnectionManager()
        self._server: Optional[uvicorn.Server] = None
        self._static_dir = Path(__file__).parent / "static"

        self._setup_routes()

    def _setup_routes(self):
        """Configure FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            """Serve the main HTML page."""
            index_path = self._static_dir / "index.html"
            if not index_path.exists():
                raise HTTPException(status_code=404, detail="index.html not found")
            return index_path.read_text()

        @self.app.get("/static/{file_path:path}")
        async def serve_static(file_path: str):
            """Serve static files."""
            full_path = self._static_dir / file_path
            if not full_path.exists() or not full_path.is_file():
                raise HTTPException(status_code=404, detail="File not found")
            return FileResponse(full_path)

        @self.app.get("/api/subsections")
        async def get_subsections():
            """Get metadata for all registered subsections."""
            if not self.registry:
                return []
            return self.registry.get_metadata_list()

        @self.app.get("/api/subsection/{name}")
        async def get_subsection_data(name: str):
            """Get initial data and template for a subsection."""
            if not self.registry:
                raise HTTPException(status_code=404, detail="Registry not initialized")

            subsection = self.registry.get(name)
            if not subsection:
                raise HTTPException(status_code=404, detail=f"Subsection '{name}' not found")

            return {
                "data": await subsection.get_initial_data(),
                "template": await subsection.get_html_template(),
            }

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Handle WebSocket connections for live updates."""
            await self.manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_json()
                    await self._handle_ws_message(websocket, data)
            except WebSocketDisconnect:
                self.manager.disconnect(websocket)
            except Exception as e:
                logger.debug(f"WebSocket error: {e}")
                self.manager.disconnect(websocket)

    async def _handle_ws_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """Handle WebSocket message from client."""
        msg_type = data.get("type")

        if msg_type == "subscribe":
            subsection_name = data.get("subsection")
            if subsection_name:
                await self.manager.subscribe(websocket, subsection_name)

        elif msg_type == "unsubscribe":
            subsection_name = data.get("subsection")
            if subsection_name:
                self.manager.unsubscribe(websocket, subsection_name)

        elif msg_type == "action":
            subsection_name = data.get("subsection")
            action = data.get("action")
            payload = data.get("data", {})

            if not self.registry:
                return

            subsection = self.registry.get(subsection_name)
            if subsection and action:
                result = await subsection.handle_action(action, payload)
                await websocket.send_json(
                    {
                        "type": "action_result",
                        "subsection": subsection_name,
                        "action": action,
                        "result": result,
                    }
                )

    async def broadcast_update(self, subsection_name: str, data: Dict[str, Any]) -> None:
        """Broadcast update to all subscribed clients."""
        await self.manager.broadcast_to_subsection(
            subsection_name,
            {
                "type": "update",
                "subsection": subsection_name,
                "data": data,
            },
        )

    async def start(self) -> None:
        """Start the web server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        """Stop the web server."""
        await self.manager.disconnect_all()
        if self._server:
            self._server.should_exit = True

    def get_url(self) -> str:
        """Get the URL for the web UI."""
        return f"http://{self.host}:{self.port}"
