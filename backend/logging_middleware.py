from fastapi import Request
import time
import logging

async def log_requests_middleware(request: Request, call_next):
    """
    Middleware mẫu để log thời gian xử lý request.
    Sẽ rất hữu ích cho việc audit sau này theo tài liệu hướng dẫn RAG.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logging.info(f"Method: {request.method} Path: {request.url.path} Time: {process_time:.4f}s")
    return response