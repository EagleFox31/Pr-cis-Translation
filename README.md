# Précis Translation Platform

A secure translation web application with a React (Vite/TypeScript/Tailwind) frontend and a FastAPI (Python) backend.

## Architecture

```
traduction_app/
├── backend/                   # FastAPI Python backend
│   ├── app.py                 # Main FastAPI application
│   ├── translator.py          # DeepSeek API integration (httpx async)
│   ├── file_handlers.py       # TXT/PDF/DOCX extraction
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # Local configuration
│   └── .env.example           # Environment variables template
├── frontend/                  # React Vite/TS/Tailwind frontend
│   ├── public/                # Static assets (mascot, PDFs, etc.)
│   ├── src/
│   │   ├── components/        # React components (SplashScreen, etc.)
│   │   ├── hooks/             # useTranslation.ts hook
│   │   ├── locales/           # i18n locales (en, fr)
│   │   ├── pages/             # Home.tsx main page
│   │   ├── App.tsx            # Main React Entrypoint
│   │   └── main.tsx           # React bootstrap
│   ├── package.json           # Vite and React dependencies
│   ├── tsconfig.json          # TS config
│   ├── vite.config.ts         # Vite proxy configuration
│   └── .env                   # Local Vite configuration
└── README.md                  # Project documentation
```

## Security Features

- **Frontend Security**: API Key verification using `X-API-Key` headers (never exposes DeepSeek key).
- **Backend Validation**: CORS settings configured to restrict access to trusted origins.
- **Rate Limiting**: Integrated `slowapi` rate limiter allowing 10 requests per minute per IP address.
- **File Limits**: Strict file size validation (max 5MB) and type validation (.txt, .pdf, .docx).
- **Data Protection**: Incoming logs exclude sensitive document contents or translations.

## Setup & Running Instructions

### 1. Copy Static Assets to Frontend
First, copy the public static assets from the root `/public` folder to `/frontend/public/` (required for logo animations and interactive PDF preview):
```bash
# From project root
mkdir -p frontend/public
cp public/* frontend/public/
```

### 2. Backend (FastAPI Python)
Open a terminal in the `backend` directory:
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env and fill in your DEEPSEEK_API_KEY
```

To run the backend development server:
```bash
uvicorn app:app --reload --port 8000
```
Verify backend is healthy by visiting `http://localhost:8000/health`.

### 3. Frontend (React Vite)
Open a new terminal in the `frontend` directory:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Vite is configured to proxy `/api` calls to the FastAPI server running on `http://localhost:8000`.

## Environment Variables

### Backend Configuration (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | Your DeepSeek developer API key | *Required* |
| `DEEPSEEK_API_URL` | DeepSeek chat completions URL | `https://api.deepseek.com/v1/chat/completions` |
| `DEEPSEEK_MODEL` | AI Model to use for translating | `deepseek-chat` |
| `FRONTEND_API_KEY` | Key verified in incoming `X-API-Key` | `precis_frontend_secure_key_2026_xK9mP2vL` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:5173,http://localhost:8000...` |

### Frontend Configuration (`frontend/.env`)

- `VITE_API_KEY` matches the backend's `FRONTEND_API_KEY` value.
- `VITE_API_BASE` points to the local backend base URL (e.g. `http://localhost:8000`).