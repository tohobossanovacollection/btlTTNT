from fastapi import HTTPException

class SampleController:
    @staticmethod
    def get_health_status():
        """Logic kiểm tra trạng thái hệ thống."""
        return {
            "status": "online",
            "components": {
                "api": "healthy",
                "ai_engine": "ready_placeholder"
            }
        }