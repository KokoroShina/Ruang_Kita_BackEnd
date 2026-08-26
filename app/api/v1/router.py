from fastapi import APIRouter

from app.api.v1 import account, ai, auth, chat, discover, health, journal, mood, topics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(account.router)
api_router.include_router(ai.router)
api_router.include_router(chat.router)
api_router.include_router(journal.router)
api_router.include_router(mood.router)
api_router.include_router(topics.router)
api_router.include_router(discover.router)
