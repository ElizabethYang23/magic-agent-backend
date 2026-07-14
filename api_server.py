"""
api_server.py

Turns query_agent.py's ask_agent() into a real web API your frontend can call.

Run locally with:
    uvicorn api_server:app --reload

Then your frontend calls, e.g.:
    POST http://localhost:8000/ask
    { "mode": "routine", "message": "Design a beginner coin routine", "user_id": "..." }

SETUP
-----
pip install fastapi uvicorn

(everything else - supabase, voyageai, anthropic - you already installed
for query_agent.py, since this file reuses its logic directly)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from query_agent import ask_agent  # reuses everything you already built

app = FastAPI(title="Magic Agent API")

# CORS: allows your frontend (running on a different URL/port) to call this API.
# For now this allows any origin, which is fine for development.
# Before your real demo, replace "*" with your actual frontend URL for safety.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    mode: str        # "routine", "script", or "training"
    message: str      # the user's chat message
    user_id: str      # the logged-in user's Supabase id


class AskResponse(BaseModel):
    reply: str


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if request.mode not in ("routine", "script", "training"):
        raise HTTPException(status_code=400, detail="mode must be 'routine', 'script', or 'training'")
    try:
        reply = ask_agent(mode=request.mode, user_message=request.message, user_id=request.user_id)
        return AskResponse(reply=reply)
    except Exception as e:
        # In development, showing the real error helps you debug fast.
        # Before your demo, you may want a more generic message here instead.
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Quick check that the server is alive - useful once this is deployed."""
    return {"status": "ok"}
