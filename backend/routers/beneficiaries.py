# routers/beneficiaries.py

from fastapi import APIRouter, HTTPException
from core.supabase import supabase

router = APIRouter()


@router.get("/")
async def list_beneficiaries():
    try:
        res = (
            supabase.table("pab_beneficiaries")
            .select(
                """
                nric,
                full_name,
                button_id,
                primary_language,
                address,
                unit_number,
                phone_number,
                emergency_contact_name,
                emergency_contact, 
                patient_medical_summary
                """
            )
            .order("full_name")
            .execute()
        )

        return {"items": res.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
