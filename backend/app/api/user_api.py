from fastapi import APIRouter
from app.services.user_service import get_all_users

router = APIRouter()

@router.get("/")
def users():
    return get_all_users()