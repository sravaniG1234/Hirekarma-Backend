from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
    
    def disconnect(self, channel: str, websocket: WebSocket):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
    
    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to WebSocket: {e}")
                    disconnected.add(connection)
            
            async with self.lock:
                self.active_connections[channel] -= disconnected
                if not self.active_connections[channel]:
                    del self.active_connections[channel]

# Global WebSocket manager instance
manager = ConnectionManager()
