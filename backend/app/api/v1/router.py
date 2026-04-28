from fastapi import APIRouter

from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.assignments import router as assignments_router
from app.api.v1.endpoints.batches import router as batches_router
from app.api.v1.endpoints.campaigns import router as campaigns_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.inbound import router as inbound_router
from app.api.v1.endpoints.imports import router as imports_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.operator_queue import router as operator_queue_router
from app.api.v1.endpoints.people import router as people_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.settings import router as settings_router
from app.api.v1.endpoints.templates import router as templates_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(audit_logs_router)
api_router.include_router(assignments_router)
api_router.include_router(people_router)
api_router.include_router(templates_router)
api_router.include_router(batches_router)
api_router.include_router(campaigns_router)
api_router.include_router(inbound_router)
api_router.include_router(imports_router)
api_router.include_router(jobs_router)
api_router.include_router(operator_queue_router)
api_router.include_router(projects_router)
api_router.include_router(settings_router)
api_router.include_router(metrics_router)
