"""
MIKE Core Server Runner.
Launches the FastAPI application and WebSocket IPC server on http://127.0.0.1:8765.
"""

import sys
import uvicorn
from core.config import settings
from core.logger import logger


def main():
    logger.info(f"Starting MIKE Core Server on {settings.server_host}:{settings.server_port}...")
    uvicorn.run(
        "core.server.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

