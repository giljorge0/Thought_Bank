# Thought Bank

A frictionless capture layer for global human ideation. Dump a raw thought, and the system maps it into a shared vector space, scores its originality, and — if many people think the same thing — synthesizes the collective insight.

This is a **third project** that draws from two existing codebases:

- **[originality_radar](https://github.com/giljorge0/originality_radar)** — multi-user pgvector infrastructure, k-NN scoring, cosine similarity math, live WebSocket map
- **[Digital-Brain-Project](https://github.com/giljorge0/Digital-Brain-Project)** — auto-wiki synthesis, relation extraction, LangGraph query agents, claim extraction

## The Three Features

### 1. "You Are Not Alone" Engine
Submit a thought. If it lands in a dense vector neighborhood (cosine similarity ≥ 0.75 with 3+ existing thoughts), the system synthesizes the cluster: how many people share this thought, what they collectively concluded, and the core insight distilled from dozens of independent minds.

### 2. Predictive Solution Market
Background DBSCAN clustering detects dense thought regions. Temporal velocity tracking (7-day vs 30-day growth rates) identifies clusters expanding exponentially — a real-time heatmap of emerging problems and opportunities.

### 3. Asynchronous Global Brainstorming
For mature clusters (10+ thoughts), an auto-wiki generator produces a living synthesis page. Atomic claims are extracted from individual thoughts (adapted from `relations.py`), contradictions flagged, and the best framings surfaced.

## Architecture

```
User Input ──▶ Ollama Embedding (nomic-embed-text, 768-dim)
                    │
                    ▼
              pgvector k-NN Query
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   High Similarity        Low Similarity
   (≥ 0.75 avg)          (< 0.75 avg)
         │                     │
         ▼                     ▼
   "You Are Not Alone"    Originality Score
   LLM Synthesis          + Drift Suggestions
         │                     │
         └──────────┬──────────┘
                    ▼
           Store + Broadcast (WebSocket)
                    │
              ┌─────┴─────┐
              ▼           ▼
        React UI      Background Jobs
        (Canvas Map)  (DBSCAN clustering,
                       velocity tracking,
                       wiki generation)
```

### From originality_radar
- `services/vector.py` — cosine similarity, scoring formula, PCA projection (ported from `vector.js`)
- `services/embeddings.py` — Ollama integration for embeddings + drift analysis (ported from `anthropic.js`)
- `db/client.py` — pgvector queries, k-NN, HNSW indexes (ported from `client.js` + migrations)
- WebSocket broadcast for live map updates

### From Digital-Brain-Project
- `agents/synthesis.py` — "You Are Not Alone" cluster synthesis (adapted from `auto_wiki.py` generation pattern)
- `analytics/clustering.py` — DBSCAN clustering + wiki generation (adapted from `auto_wiki.py` scheduled refresh)
- Claim extraction and contradiction detection (adapted from `relations.py`)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + Vite, D3-style canvas map |
| **Backend** | Python 3.10+ / FastAPI |
| **Vector DB** | PostgreSQL + pgvector (Supabase compatible) |
| **Embeddings** | Ollama (`nomic-embed-text`, 768-dim) |
| **Analysis LLM** | Ollama (`mistral`) — no API keys needed |
| **Background** | APScheduler (clustering every 6h, velocity every 1h) |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ with pgvector
- [Ollama](https://ollama.com) running locally:
  ```bash
  ollama pull nomic-embed-text
  ollama pull mistral
  ```

### 1. Clone & Install

```bash
git clone https://github.com/giljorge0/thought-bank.git
cd thought-bank

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Database

Create a PostgreSQL database and enable pgvector:
```sql
CREATE DATABASE thought_bank;
\c thought_bank
CREATE EXTENSION IF NOT EXISTS vector;
```

The FastAPI backend runs migrations automatically on startup.

### 3. Environment

```bash
cp backend/.env.example backend/.env
# Edit DATABASE_URL in backend/.env
```

### 4. Run

```bash
# Terminal 1 — Backend
cd backend
source venv/bin/activate
python main.py
# → Thought Bank on http://localhost:8000

# Terminal 2 — Frontend
cd frontend
npm run dev
# → http://localhost:5173
```

## Project Structure

```
thought-bank/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ThoughtInput.jsx      # Frictionless capture
│   │   │   ├── ResultCard.jsx        # Score + YANA synthesis + drift
│   │   │   └── ThoughtMap.jsx        # Canvas vector space visualization
│   │   ├── hooks/
│   │   │   └── useWebSocket.js       # Live multiplayer (from originality_radar)
│   │   ├── api/
│   │   │   └── client.js             # API hooks
│   │   ├── App.jsx
│   │   └── app.css
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── backend/
│   ├── main.py                       # FastAPI app + WebSocket + scheduler
│   ├── db/
│   │   ├── client.py                 # Async pgvector client
│   │   └── migrations/
│   │       └── 001_create_thoughts.sql
│   ├── services/
│   │   ├── embeddings.py             # Ollama embedding + synthesis + wiki
│   │   └── vector.py                 # Cosine math, scoring, PCA projection
│   ├── agents/
│   │   └── synthesis.py              # "You Are Not Alone" pipeline
│   ├── analytics/
│   │   └── clustering.py             # DBSCAN + velocity + wiki generation
│   ├── requirements.txt
│   └── .env.example
│
└── docs/
```

## API Reference

### `POST /api/thoughts/submit`
Submit a thought. Returns originality score, drift analysis, and (if dense neighborhood) "You Are Not Alone" synthesis.

### `GET /api/thoughts/map?domain=Tech`
All thoughts with 2D coordinates for visualization.

### `GET /api/thoughts/stats`
Aggregate statistics.

### `GET /api/clusters`
All detected clusters with wiki content.

### `GET /api/trends/predictive`
Trending clusters (accelerating growth velocity).

### `WS /ws`
Live thought broadcast. Receives `NEW_THOUGHT` events.

## Roadmap

- [x] "You Are Not Alone" engine (Phase 1)
- [x] pgvector schema with cluster support
- [x] Originality scoring + drift analysis
- [x] Live WebSocket map
- [x] DBSCAN clustering + wiki generation (Phase 2)
- [x] Velocity tracking + trend detection (Phase 3)
- [ ] User accounts
- [ ] D3.js force-directed cluster visualization
- [ ] Mobile app
- [ ] Multi-language support

## License

MIT
