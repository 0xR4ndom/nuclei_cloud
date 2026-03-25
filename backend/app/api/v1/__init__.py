from fastapi import APIRouter
from app.api.v1 import auth, users, targets, scans, findings, webhooks, templates

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(targets.router)
api_router.include_router(scans.router)
api_router.include_router(findings.router)
api_router.include_router(webhooks.router)
api_router.include_router(templates.router)
