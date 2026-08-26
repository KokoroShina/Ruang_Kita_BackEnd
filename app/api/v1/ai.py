"""Endpoint test AI Gateway — verifikasi end-to-end sebelum fitur Pahami/Kenali dibangun.

Akan tetap berguna sebagai health-check AI setelah chat service jadi.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser
from app.schemas.ai import AITestRequest, AITestResponse, AttemptRead
from app.services.ai.openrouter_client import OpenRouterAuthError
from app.services.ai.router import (
    AIConfigurationError,
    AIGatewayError,
    CrisisDetectedError,
    generate_text,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/test",
    response_model=AITestResponse,
    summary="Test AI Gateway end-to-end (fallback + guardrail + logging)",
)
async def ai_test(payload: AITestRequest, current_user: CurrentUser) -> AITestResponse:
    messages: list[dict[str, str]] = [{"role": "user", "content": payload.message}]
    try:
        result = await generate_text(
            messages=messages,
            endpoint_type="test",
            user_id=current_user.id if isinstance(current_user.id, uuid.UUID) else current_user.id,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except CrisisDetectedError as exc:
        # Jalur berbeda: BUKAN error — kontrak respons khusus untuk frontend
        return AITestResponse(
            crisis_detected=True,
            detail=(
                "Pesanmu mengandung indikasi yang butuh perhatian lebih. "
                f"(terdeteksi pada: {exc.source})"
            ),
            attempts=[],
        )
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Konfigurasi AI bermasalah: {exc}",
        ) from exc
    except (AIGatewayError, OpenRouterAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AITestResponse(
        crisis_detected=False,
        response=result.content,
        model_used=result.model_used,
        attempts=[
            AttemptRead(model=a.model, ok=a.ok, error=a.error) for a in result.attempts
        ],
        latency_ms=result.latency_ms,
    )
