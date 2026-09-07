from fastapi import APIRouter
from .import_review import router as import_review_router

from . import accounts, dashboard, data, members, snapshots


api_router = APIRouter(prefix="/api")
api_router.include_router(import_review_router)
api_router.include_router(dashboard.router)
api_router.include_router(members.router)
api_router.include_router(accounts.router)
api_router.include_router(snapshots.router)
api_router.include_router(data.router)
