from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio

from app.core.config import get_settings
from app.infrastructure.storage.mongodb import get_mongodb
from app.infrastructure.storage.redis import get_redis
from app.interfaces.dependencies import get_agent_service
from app.interfaces.api.routes import router
from app.infrastructure.logging import setup_logging
from app.interfaces.errors.exception_handlers import register_exception_handlers
from app.infrastructure.models.documents import (
    AgentDocument,
    SessionDocument,
    UserDocument,
)
from beanie import init_beanie
from datetime import datetime, timedelta, timezone
from app.domain.models.session import SessionStatus

# Initialize logging system
setup_logging()
logger = logging.getLogger(__name__)

# Load configuration
settings = get_settings()


# Create lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code executed on startup
    logger.info("Application startup - iManus AI Agent initializing")

    # Initialize MongoDB and Beanie
    await get_mongodb().initialize()

    # Initialize Beanie
    await init_beanie(
        database=get_mongodb().client[settings.mongodb_database],
        document_models=[AgentDocument, SessionDocument, UserDocument],
    )
    logger.info("Successfully initialized Beanie")

    # Initialize Redis
    await get_redis().initialize()

    # Start background task to cleanup stale RUNNING sessions
    cleanup_task = None

    async def _cleanup_stale_sessions():
        """Background task: mark stale RUNNING sessions as COMPLETED

        A session is considered stale when its `latest_message_at` (or `updated_at`) is
        older than `session_stale_seconds` (default 60*60*24s). This prevents sessions from
        remaining in RUNNING state indefinitely.
        """
        session_stale_seconds = getattr(settings, "session_stale_seconds", 60*60*24)
        while True:
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    seconds=session_stale_seconds
                )
                # Find sessions that are RUNNING and have no recent updates
                query = {
                    "status": SessionStatus.RUNNING,
                    "$or": [
                        {"latest_message_at": {"$lt": cutoff}},
                        {"latest_message_at": None},
                        {"updated_at": {"$lt": cutoff}},
                    ],
                }
                docs = await SessionDocument.find(query).to_list()
                if docs:
                    for doc in docs:
                        try:
                            doc.status = SessionStatus.COMPLETED
                            doc.updated_at = datetime.now(timezone.utc)
                            await doc.save()
                            logger.info(
                                f"Marked stale session {doc.session_id} as COMPLETED"
                            )
                        except Exception:
                            logger.exception(
                                f"Failed to mark session {doc.session_id} as COMPLETED"
                            )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in cleanup stale sessions task")
                await asyncio.sleep(60)

    cleanup_task = asyncio.create_task(_cleanup_stale_sessions())

    try:
        yield
    finally:
        # Code executed on shutdown
        logger.info("Application shutdown - iManus AI Agent terminating")
        # Disconnect from MongoDB
        await get_mongodb().shutdown()
        # Disconnect from Redis
        await get_redis().shutdown()

        logger.info("Cleaning up AgentService instance")
        try:
            await asyncio.wait_for(get_agent_service().shutdown(), timeout=30.0)
            logger.info("AgentService shutdown completed successfully")
        except asyncio.TimeoutError:
            logger.warning("AgentService shutdown timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Error during AgentService cleanup: {str(e)}")
        # Cancel cleanup task if running
        try:
            if cleanup_task:
                cleanup_task.cancel()
                await asyncio.wait_for(cleanup_task, timeout=5.0)
                logger.info("Cleanup stale sessions task stopped")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error stopping cleanup task")


app = FastAPI(title="iManus AI Agent", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Register routes
app.include_router(router, prefix="/api/v1")
