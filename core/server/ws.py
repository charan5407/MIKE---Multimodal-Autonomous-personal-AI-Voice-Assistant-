"""
WebSocket Connection Manager for MIKE.
Handles bidirectional real-time communication between Python Core and Desktop UI.
"""

import json
from typing import Any, Dict, List
from fastapi import WebSocket
from core.logger import logger


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Desktop UI connected via WebSocket. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Desktop UI disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, event: str, payload: Dict[str, Any]):
        """Broadcasts a JSON message to all connected clients."""
        if not self.active_connections:
            return

        message = json.dumps({"event": event, "data": payload})
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


# Global WebSocket connection manager
ws_manager = ConnectionManager()
