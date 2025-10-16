from fastapi import APIRouter
from ..config import get_settings

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])

@router.get("/status")
def llm_status():
    s = get_settings()
    return {
        "configured": bool(s.openai_api_key),
        "base_url": s.openai_base_url or "https://api.openai.com/v1",
        "model": s.openai_model,
    }
