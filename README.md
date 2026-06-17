# Thought Bank 🧠

> Drop a raw thought. The system maps it into a shared vector space, scores its originality, and — when enough people share it — synthesises the collective insight.

![Python](https://img.shields.io/badge/Python-3.10+-7F77DD?style=flat-square&labelColor=1a1a2e)
![FastAPI](https://img.shields.io/badge/FastAPI-async-7F77DD?style=flat-square&labelColor=1a1a2e)
![pgvector](https://img.shields.io/badge/pgvector-HNSW-1D9E75?style=flat-square&labelColor=1a1a2e)
![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-1D9E75?style=flat-square&labelColor=1a1a2e)
![React](https://img.shields.io/badge/React-18-6366f1?style=flat-square&labelColor=1a1a2e)
![License](https://img.shields.io/badge/license-MIT-888?style=flat-square&labelColor=1a1a2e)

---

## What it does

Submit any thought — no title, no tags, no friction. The backend embeds it into a 768-dimensional vector space, runs a k-NN query against every previous submission, and returns:

- An **originality score** (0–100) based on cosine similarity
- A **density label** (SATURATED → VOID) showing how crowded that region of thought-space is
- The **nearest existing thoughts** and their similarity percentages
- A **"You Are Not Alone"** synthesis card if 3+ people have thought something similar — showing the count, the collective core insight, and key recurring themes
- A **drift suggestion** for how to push the idea further into unexplored territory

Everything feeds into a **live WebSocket map** where dots appear in real-time as thoughts come in from anyone connected.

---

## The three features

### 1. You Are Not Alone
Write down a highly specific anxiety or a niche idea. If the vector neighborhood is dense enough (cosine similarity ≥ 0.75 across 3+ existing thoughts), the system synthesises them into a validating response:

```
5 other people have submitted a very similar thought.

Core insight: Fear of existential risk drives independent convergence on space colonisation.

Themes: multi-planetary · extinction risk · space colonisation
```

### 2. Predictive Solution Market
Background DBSCAN clustering detects dense thought regions. 7-day vs 30-day velocity tracking flags clusters with accelerating growth — a real-time signal for which problems are becoming urgent before they're obvious.

```
GET /api/trends/predictive
→ clusters sorted by velocity_7d / velocity_30d ratio
```

### 3. Asynchronous Global Brainstorming
For mature clusters (10+ thoughts), an auto-wiki generator synthesises the best framings into a living page. Atomic claims are extracted and contradictions flagged. Pages update incrementally as new thoughts arrive.

---

## How a thought is processed

```
User input
    ↓
nomic-embed-text via Ollama → 768-dim vector
    ↓
pgvector HNSW k-NN → 10 nearest neighbors (<100ms)
    ↓
score = (1 − avgSim) × 100
    ↓
if neighbors with sim ≥ 0.75 ≥ 3:
    → fetch full neighborhood (up to 50)
    → mistral synthesises "You Are Not Alone" response
else:
    → mistral generates drift suggestion
    ↓
2D PCA projection → map coordinates
    ↓
store in PostgreSQL + broadcast via WebSocket
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / FastAPI / asyncpg |
| Frontend | React 18 / Vite |
| Vector DB | PostgreSQL 14+ / pgvector (HNSW index) |
| Embeddings | Ollama — `nomic-embed-text` (768-dim) |
| Analysis LLM | Ollama — `mistral` |
| Clustering | scikit-learn DBSCAN |
| Background jobs | APScheduler (clustering 6h, velocity 1h) |
| Realtime | WebSocket broadcast |

No API keys. Runs entirely locally via Ollama.

---

## Project structure

```
thought-bank/
├── backend/
│   ├── main.py                     # FastAPI routes + WebSocket
│   ├── agents/synthesis.py         # "You Are Not Alone" pipeline
│   ├── analytics/clustering.py     # DBSCAN + auto-wiki + velocity
│   ├── services/
│   │   ├── embeddings.py           # Ollama integration
│   │   └── vector.py               # Cosine math + PCA projection
│   ├── db/
│   │   ├── client.py               # Async pgvector client
│   │   └── migrations/001_...sql   # Schema
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── ThoughtInput.jsx     # Frictionless capture
    │   │   ├── ResultCard.jsx       # Score + YANA + drift
    │   │   └── ThoughtMap.jsx       # Canvas vector space
    │   └── hooks/useWebSocket.js    # Live updates
    └── package.json
```

---

## Quick start

### Prerequisites

```bash
# Ollama running locally with models pulled
ollama pull nomic-embed-text
ollama pull mistral

# PostgreSQL with pgvector
createdb thought_bank
psql thought_bank -c "CREATE EXTENSION vector;"
```

### Docker (one command)

```bash
git clone https://github.com/giljorge0/thought-bank
cd thought-bank
docker-compose up
# Then in another terminal:
docker exec thought-bank-ollama-1 ollama pull nomic-embed-text mistral
```

Open http://localhost:5173

### Manual

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # set DATABASE_URL
python3 main.py

# Frontend (new terminal)
cd frontend
npm install && npm run dev
```

---

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/thoughts/submit` | Submit a thought → score + synthesis |
| `GET /api/thoughts/map?domain=Tech` | All thoughts with 2D coordinates |
| `GET /api/thoughts/stats` | Aggregate statistics |
| `GET /api/clusters` | All clusters with wiki content |
| `GET /api/trends/predictive` | Trending clusters (Phase 3) |
| `WS /ws` | Live thought broadcast |
| `POST /api/admin/cluster-now` | Trigger DBSCAN clustering |

---

## Scoring

```python
# k-NN query: 10 nearest neighbors by cosine distance
similarities = [sim(new_vec, neighbor) for neighbor in top_10]
avg_sim = mean(similarities)
score = round((1 - avg_sim) * 100)

# Density labels
0–15   → SATURATED   # heavily explored territory
16–35  → DENSE
36–55  → POPULATED
56–75  → SPARSE
76–90  → FRONTIER
91–100 → VOID        # unexplored
```

---

## Related projects

This project draws from two existing codebases:

- **[originality_radar](https://github.com/giljorge0/originality_radar)** — multi-user pgvector infrastructure, k-NN scoring, cosine similarity math, live WebSocket map. The vector math (`vector.py`), Ollama integration (`embeddings.py`), and database schema are ported from there.

- **[Digital-Brain-Project](https://github.com/giljorge0/Digital-Brain-Project)** — auto-wiki synthesis, relation extraction, claim extraction, LangGraph query agents. The synthesis pipeline (`agents/synthesis.py`) and clustering wiki generation (`analytics/clustering.py`) adapt patterns from `auto_wiki.py` and `relations.py`.

Thought Bank is the third project: a new repo that extracts the multi-user vector layer from originality_radar and powers it with the neuro-symbolic synthesis agents from Digital-Brain-Project.

---

## Roadmap

- [x] "You Are Not Alone" engine
- [x] Originality scoring + density labels
- [x] Drift suggestions
- [x] 2D canvas map + WebSocket live updates
- [x] DBSCAN clustering + auto-wiki generation
- [x] Temporal velocity tracking + trend detection
- [ ] Force-directed cluster visualization (D3.js)
- [ ] User accounts (personal thought journey)
- [ ] `query_agent.py` endpoint — "ask the cluster a question"
- [ ] Mobile app

---

## License

MIT
