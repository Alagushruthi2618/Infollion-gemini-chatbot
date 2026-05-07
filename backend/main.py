import base64
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel
from pypdf import PdfReader

load_dotenv()

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_CHARS = 60_000
MAX_HISTORY_MESSAGES = 12

ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

app = FastAPI(title="Gemini Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chats: Dict[str, dict] = {}


class MessageRequest(BaseModel):
    message: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_chat() -> dict:
    chat_id = str(uuid.uuid4())
    timestamp = now_iso()
    chat = {
        "id": chat_id,
        "title": "New chat",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "messages": [],
        "document": None,
        "image": None,
    }
    chats[chat_id] = chat
    return chat


def public_message(message: dict) -> dict:
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "createdAt": message["createdAt"],
    }


def public_chat(chat: dict, include_messages: bool = True) -> dict:
    result = {
        "id": chat["id"],
        "title": chat["title"],
        "createdAt": chat["createdAt"],
        "updatedAt": chat["updatedAt"],
        "document": chat["document"]
        and {
            "name": chat["document"]["name"],
            "chars": len(chat["document"]["text"]),
        },
        "image": chat["image"]
        and {
            "name": chat["image"]["name"],
            "mimeType": chat["image"]["mimeType"],
            "preview": chat["image"]["preview"],
        },
    }
    if include_messages:
        result["messages"] = [public_message(message) for message in chat["messages"]]
    return result


def get_chat_or_404(chat_id: str) -> dict:
    chat = chats.get(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


async def read_limited_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File must be 8 MB or smaller")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return data


def validate_extension(filename: Optional[str], allowed_extension: str) -> None:
    if not filename or not filename.lower().endswith(allowed_extension):
        raise HTTPException(
            status_code=400,
            detail=f"File extension must be {allowed_extension}",
        )


def extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(page.strip() for page in pages if page.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read PDF text") from exc
    if not text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")
    return text[:MAX_DOCUMENT_CHARS]


def extract_txt_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=400, detail="Could not decode text file")
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text file has no readable content")
    return text[:MAX_DOCUMENT_CHARS]


def add_message(chat: dict, role: str, content: str) -> dict:
    message = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "createdAt": now_iso(),
    }
    chat["messages"].append(message)
    chat["updatedAt"] = message["createdAt"]
    if role == "user" and chat["title"] == "New chat":
        chat["title"] = content.strip()[:36] or "New chat"
    return message


def build_contents(chat: dict, user_message: str) -> List[types.Content]:
    contents: List[types.Content] = []
    prior_messages = chat["messages"][-MAX_HISTORY_MESSAGES:]

    for message in prior_messages:
        role = "model" if message["role"] == "bot" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=message["content"])],
            )
        )

    prompt_parts: List[types.Part] = []
    context_lines = [
        "You are a helpful chatbot. Answer naturally and use the available chat context.",
    ]

    if chat["document"]:
        context_lines.append(
            "Uploaded document text:\n"
            f"Filename: {chat['document']['name']}\n"
            f"{chat['document']['text']}"
        )
    else:
        context_lines.append("No document has been uploaded in this chat.")

    if chat["image"]:
        context_lines.append(f"An uploaded image is available: {chat['image']['name']}.")
        prompt_parts.append(
            types.Part.from_bytes(
                data=chat["image"]["bytes"],
                mime_type=chat["image"]["mimeType"],
            )
        )
    else:
        context_lines.append("No image has been uploaded in this chat.")

    context_lines.append(f"Current user message: {user_message}")
    prompt_parts.append(types.Part(text="\n\n".join(context_lines)))

    contents.append(types.Content(role="user", parts=prompt_parts))
    return contents


def ask_gemini(chat: dict, user_message: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured on the backend",
        )

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        response = client.models.generate_content(
            model=model,
            contents=build_contents(chat, user_message),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")
    return text.strip()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/chats")
def list_chats() -> dict:
    ordered = sorted(chats.values(), key=lambda chat: chat["updatedAt"], reverse=True)
    return {"chats": [public_chat(chat, include_messages=False) for chat in ordered]}


@app.post("/api/chats")
def create_chat() -> dict:
    return {"chat": public_chat(make_chat())}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str) -> dict:
    return {"chat": public_chat(get_chat_or_404(chat_id))}


@app.post("/api/chats/{chat_id}/message")
def send_message(chat_id: str, request: MessageRequest) -> dict:
    chat = get_chat_or_404(chat_id)
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    bot_text = ask_gemini(chat, user_message)
    add_message(chat, "user", user_message)
    add_message(chat, "bot", bot_text)
    return {"chat": public_chat(chat)}


@app.post("/api/chats/{chat_id}/upload/document")
async def upload_document(chat_id: str, file: UploadFile = File(...)) -> dict:
    chat = get_chat_or_404(chat_id)
    mime_type = file.content_type
    if mime_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF and TXT documents are allowed")
    validate_extension(file.filename, ALLOWED_DOC_TYPES[mime_type])

    data = await read_limited_upload(file)
    text = extract_pdf_text(data) if mime_type == "application/pdf" else extract_txt_text(data)

    chat["document"] = {
        "name": file.filename,
        "mimeType": mime_type,
        "text": text,
    }
    chat["updatedAt"] = now_iso()
    return {"chat": public_chat(chat)}


@app.post("/api/chats/{chat_id}/upload/image")
async def upload_image(chat_id: str, file: UploadFile = File(...)) -> dict:
    chat = get_chat_or_404(chat_id)
    mime_type = file.content_type
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG and JPG images are allowed")
    extension = ".png" if mime_type == "image/png" else (".jpg", ".jpeg")
    if isinstance(extension, tuple):
        if not file.filename or not file.filename.lower().endswith(extension):
            raise HTTPException(status_code=400, detail="File extension must be .jpg or .jpeg")
    else:
        validate_extension(file.filename, extension)

    data = await read_limited_upload(file)
    preview = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"

    chat["image"] = {
        "name": file.filename,
        "mimeType": mime_type,
        "bytes": data,
        "preview": preview,
    }
    chat["updatedAt"] = now_iso()
    return {"chat": public_chat(chat)}
