"""
Metrics Router - Prometheus Endpoint

Exposes /metrics endpoint for Prometheus scraping
"""
from fastapi import APIRouter, Response
from ..metrics import get_metrics_text, get_metrics_content_type

router = APIRouter(tags=["Observability"])


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint

    Returns metrics in Prometheus text format for scraping.

    Security Note:
    - This endpoint should be protected in production (IP allowlist or auth)
    - Exposes operational metrics but no sensitive data
    """
    return Response(
        content=get_metrics_text(),
        media_type=get_metrics_content_type()
    )
