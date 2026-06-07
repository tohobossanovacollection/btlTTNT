from fastapi import APIRouter
from app.controllers.sample_controller import SampleController

router = APIRouter()

@router.get("/health", tags=["System"])
async def health_check():
    """Kiểm tra trạng thái hoạt động của Backend."""
    return SampleController.get_health_status()

@router.get("/hello", tags=["Test"])
async def say_hello(name: str = "Developer"):
    """Endpoint mẫu để test API."""
    return {"message": f"Hello {name}, your new backend is ready!"}