import asyncio
import json

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse

from api.auth import verify_key
from api.models import ChatRequest
from main import run_agent

app = FastAPI(title="Career Intelligence Agent")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", dependencies=[Depends(verify_key)])
async def chat(body: ChatRequest):
    async def event_stream():
        yield f"data: {json.dumps({'status': 'processing'})}\n\n"
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, run_agent, body.message, body.thread_id
        )
        yield f"data: {json.dumps({'done': True, 'response': response})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
