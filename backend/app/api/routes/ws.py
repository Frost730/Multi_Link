import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.events import event_bus
from app.networking.bandwidth_monitor import bandwidth_monitor
import logging

logger = logging.getLogger("multilink.ws")
router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/downloads")
async def websocket_downloads_endpoint(websocket: WebSocket):
    await websocket.accept()
    queue = event_bus.subscribe()
    logger.info("New WebSocket client connected.")

    # Send initial status
    try:
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {
                "combined_speed_bps": bandwidth_monitor.get_combined_speed(),
                "history": [p.model_dump() for p in bandwidth_monitor.get_history()]
            }
        }))
    except Exception as e:
        logger.debug(f"Error sending welcome packet: {e}")

    try:
        while True:
            # Wait for event from event bus
            event = await queue.get()
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"WebSocket send loop error: {e}")
    finally:
        event_bus.unsubscribe(queue)
