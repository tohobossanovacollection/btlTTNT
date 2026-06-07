from fastapi import APIRouter
from app.controllers.sample_controller import SampleController

router = APIRouter(prefix="/system", tags=["System"])

@router.get("/health")
async def health_check():
    """Kiểm tra trạng thái hoạt động của Backend."""
    return SampleController.get_health_status()

@router.get("/hello")
async def say_hello(name: str = "Developer"):
    """Endpoint mẫu để test API."""
    return {
        "message": f"Hello {name}, your new clean backend is up and running!"
    }