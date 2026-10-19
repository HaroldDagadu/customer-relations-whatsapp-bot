import asyncio
import logging

logger = logging.getLogger(__name__)

async def cleanup_sessions_worker():
    """Periodically clean up expired agent sessions."""
    from session_manager import session_manager
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        try:
            session_manager.cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
