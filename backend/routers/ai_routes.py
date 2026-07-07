"""AI endpoints — trade explainer (streaming) + signal explainer (one-shot)
+ anomaly sweep status.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

from auth import get_current_user
from models import User
from services.ai_engine import explain_signal, stream_explanation
from services.anomaly_sweep import anomaly_sweeper

router = APIRouter(prefix="/ai", tags=["ai"])


class AskRequest(BaseModel):
    prompt: str
    session_id: str = "default"


@router.post("/explain")
async def explain(body: AskRequest, user: User = Depends(get_current_user)):
    session_id = f"{user.id}:{body.session_id}"

    async def gen():
        async for chunk in stream_explanation(session_id, body.prompt):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ExplainSignalRequest(BaseModel):
    symbol: str
    kind: str
    price: float
    change_pct: float = 0
    volume_ratio: float = 1.0
    confidence: float = 0.5
    ts: Optional[str] = None


@router.post("/explain-signal")
async def explain_signal_endpoint(body: ExplainSignalRequest,
                                  user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """One-shot trade explanation — used by the "Why?" button on signals."""
    session_id = f"{user.id}:explain-signal:{body.symbol}:{body.kind}"
    return await explain_signal(session_id, body.model_dump())


@router.get("/anomaly-sweep/status")
async def anomaly_sweep_status(user: User = Depends(get_current_user)):
    return anomaly_sweeper.stats()
