# Gemini Chatbot

A minimal web chatbot that uses Google's Gemini API with:

- Text conversation
- PDF/TXT document upload
- PNG/JPG image upload with preview
- In-memory chat context
- New Chat reset
- Multiple chats listed in the UI
- Loading states for uploads and responses

## Live Demo

Frontend: https://infollion-gemini-chatbot.vercel.app/

Backend Health Check: https://infollion-gemini-chatbot.onrender.com/api/health

## Tech Stack

- Frontend: React + Vite
- Backend: FastAPI
- AI Model: Google Gemini API
- Deployment:
  - Frontend → Vercel
  - Backend → Render

A minimal web chatbot that uses Google's Gemini API with:

- Text conversation
- PDF/TXT document upload
- PNG/JPG image upload with preview
- In-memory chat context
- New Chat reset
- Multiple chats listed in the UI
- Loading states for uploads and responses

## Project Structure

```text
backend/   FastAPI API, Gemini integration, file parsing, memory state
frontend/  React + Vite chat UI
```

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
FRONTEND_ORIGIN=http://localhost:5173
```

Run the backend:

```bash
uvicorn main:app --reload --port 8000
```

## Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite will print the local URL, usually:

```text
http://localhost:5173
```

If your backend is not on port `8000`, create `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8000
```

## Example Usage

1. Click **New Chat** to start with fresh context.
2. Upload a PDF or TXT file, then ask: `Summarize the document.`
3. Ask a follow-up: `What was the third point mentioned?`
4. Upload a PNG or JPG image, then ask: `What's in the image?`
5. Ask a follow-up: `Is the person smiling?`
6. Click **New Chat** and ask: `What did I upload earlier?`

The new chat has no access to previous messages or uploads.

## Notes

- Chat state is stored in backend memory only.
- State disappears when the backend restarts.
- No database, authentication, deployment, RAG, embeddings, or chunking are included.
- Upload size is limited to 8 MB per file.
