from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="Equipment Documentation Registry")

app.include_router(api_router)