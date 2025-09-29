from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# ⬇️ import the function you just added
from FYP_chatbot_LEE_YEN_YEN import generate_reply_api  # or from <your_big_file> import generate_reply_api

app = FastAPI(title="FYP Rule-based Chatbot API")

# Allow local dev frontends (adjust ports as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080", "http://localhost:8080",  # python -m http.server
        "http://127.0.0.1:5500", "http://localhost:5500",  # VS Code Live Server
        "http://127.0.0.1:3000", "http://localhost:3000",  # other dev servers
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatIn(BaseModel):
    message: str
    context: dict | None = None

class ChatOut(BaseModel):
    reply: str
    context: dict

@app.get("/")
def health():
    return {"status": "OK"}

@app.post("/chat", response_model=ChatOut)
def chat(incoming: ChatIn):
    reply, new_ctx = generate_reply_api(incoming.message, incoming.context or {})
    return ChatOut(reply=reply, context=new_ctx)
