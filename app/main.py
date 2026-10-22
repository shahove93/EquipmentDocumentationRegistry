from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import get_settings
from app.logging_config import configure_logging, shutdown_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Enable the persistent journal for the whole application lifetime."""
    configure_logging(get_settings().LOG_FILE)
    try:
        yield
    finally:
        shutdown_logging()


app = FastAPI(title="Equipment Documentation Registry", lifespan=lifespan)

app.include_router(api_router)
