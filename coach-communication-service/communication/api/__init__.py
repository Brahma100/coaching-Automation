from fastapi import APIRouter

from communication.api import analytics, messages, providers, rules, telegram_linking, templates

router = APIRouter(prefix="/api")
router.include_router(providers.router)
router.include_router(rules.router)
router.include_router(templates.router)
router.include_router(messages.router)
router.include_router(analytics.router)
router.include_router(telegram_linking.router)
