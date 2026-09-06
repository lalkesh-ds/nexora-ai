from fastapi import Request
from fastapi.responses import JSONResponse
from backend.logger import logger

async def catch_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)}
        )
