from fastapi import HTTPException, Depends

def check_admin(role: str):

    if role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền truy cập"
        )