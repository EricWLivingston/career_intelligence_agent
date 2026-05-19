import os

from fastapi import Header, HTTPException


async def verify_key(x_api_key: str = Header(...)):
    expected = os.environ.get("APP_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
