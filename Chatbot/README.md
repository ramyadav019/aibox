# AI Chatbot

A LangGraph-powered chatbot with React frontend and FastAPI backend.

## Project Structure

```
├── backend.py          # FastAPI + LangGraph backend
├── src/
│   ├── App.tsx         # Main React chat component
│   ├── App.css         # Styles
│   └── main.tsx        # Entry point
├── index.html          # Vite entry point
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Development

### Backend (Terminal 1)
```bash
pip install -r requirements.txt  # or install dependencies manually
python backend.py
```
Runs on http://localhost:8000

### Frontend (Terminal 2)
```bash
npm install
npm run dev
```
Runs on http://localhost:5173 (proxies /chat to backend)

## Production Build
```bash
npm run build
```
Output in `dist/` - serve with any static file server or configure FastAPI to serve it.