# Backend

FastAPI backend for the Gemini chatbot.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set:

```bash
GEMINI_API_KEY=your_key_here
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

API health check: `http://localhost:8000/api/health`
