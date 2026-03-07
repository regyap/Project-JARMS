from fastapi import APIRouter, HTTPException
from core.supabase import supabase

router = APIRouter()


@router.get("/")
async def list_cases():
    try:
        response = (
            supabase.table("cases").select("*").order("opened_at", desc=True).execute()
        )
        return {"items": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def create_test_case():
    payload = {
        "button_id": "BTN-001",
        "status": "new",
        "urgency_bucket": "unknown",
        "queue_score": 70,
        "source": "pab_audio",
    }

    try:
        response = supabase.table("cases").insert(payload).execute()
        return {"created": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
