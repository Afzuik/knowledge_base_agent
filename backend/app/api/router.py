from fastapi import APIRouter

from app.api.routes import chat, health, notebooks, notes, sources

api_router = APIRouter()
for router in (health.router, notebooks.router, sources.router, chat.router, notes.router):
    api_router.include_router(router)
