"""
Thought Bank — FastAPI Backend
──────────────────────────────
API endpoints, WebSocket broadcast, and background scheduler.
"""

import asyncio
import hashlib
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

from db import client as db
from agents.synthesis import process_thought
from analytics.clustering import run_clustering, compute_trend_velocity


# ── WebSocket Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active[:]:
            try:
                await ws.send_json(data)
            except Exception:
                self.active.remove(ws)

manager = ConnectionManager()


# ── Rate Limiter ─────────────────────────────────────────────────────────────

_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 5   # max scans
RATE_WINDOW = 60  # per seconds


def check_rate(ip: str) -> bool:
    now = time.time()
    hits = _rate_store.get(ip, [])
    hits = [t for t in hits if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        return False
    hits.append(now)
    _rate_store[ip] = hits
    return True


# ── App Lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Thought Bank...")
    await db.get_pool()
    # Run migrations on startup
    try:
        await db.run_migrations()
    except Exception as e:
        log.warning(f"Migration note: {e}")

    # Start background scheduler for clustering
    _start_scheduler()

    yield
    await db.close_pool()
    log.info("Thought Bank shut down.")


app = FastAPI(title="Thought Bank", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Background Scheduler ────────────────────────────────────────────────────

def _start_scheduler():
    """Run clustering + velocity updates on a schedule."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        # Clustering every 6 hours
        scheduler.add_job(run_clustering, "interval", hours=6,
                          id="clustering", replace_existing=True)
        # Velocity every hour
        scheduler.add_job(compute_trend_velocity, "interval", hours=1,
                          id="velocity", replace_existing=True)
        scheduler.start()
        log.info("✓ Background scheduler started (clustering=6h, velocity=1h)")
    except ImportError:
        log.warning("APScheduler not installed — background jobs disabled")


# ── Request Models ───────────────────────────────────────────────────────────

class ThoughtSubmission(BaseModel):
    thought: str = Field(..., min_length=3, max_length=2000)


# ── API Routes ───────────────────────────────────────────────────────────────

@app.post("/api/thoughts/submit")
async def submit_thought(body: ThoughtSubmission, request: Request):
    """
    Submit a thought for analysis.
    Returns originality score, density, drift analysis,
    and "You Are Not Alone" synthesis if the thought matches a dense cluster.
    """
    ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]

    if not check_rate(ip_hash):
        raise HTTPException(429, "Rate limit exceeded. Try again in a minute.")

    result = await process_thought(
        thought_text=body.thought,
        ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent", ""),
    )

    # Broadcast to all WebSocket clients
    await manager.broadcast({
        "type": "NEW_THOUGHT",
        "payload": {
            "id": result["id"],
            "thought": result["thought"],
            "score": result["score"],
            "density": result["density"],
            "domain": result["domain"],
            "mapCoordinates": result["mapCoordinates"],
            "createdAt": result["createdAt"],
        },
    })

    return result


@app.get("/api/thoughts/map")
async def get_map(domain: str = None):
    """Fetch all thoughts with 2D coordinates for visualization."""
    thoughts = await db.get_thoughts_for_map(domain)
    analytics = await db.get_analytics()

    return {
        "totalThoughts": analytics.get("total_thoughts", 0),
        "thoughts": [
            {
                "id": str(t["id"]),
                "thought": t["thought"],
                "score": t["score"],
                "density": t["density"],
                "domain": t["domain"],
                "mapCoordinates": {"x": t["map_x"], "y": t["map_y"]},
                "clusterId": str(t["cluster_id"]) if t["cluster_id"] else None,
                "createdAt": t["created_at"].isoformat(),
            }
            for t in thoughts
        ],
        "stats": {
            "avgScore": round(analytics.get("avg_score", 0), 1),
            "saturationPercent": round(analytics.get("saturation_percent", 0), 1),
            "frontierPercent": round(analytics.get("frontier_percent", 0), 1),
        },
    }


@app.get("/api/thoughts/stats")
async def get_stats():
    """Aggregate statistics."""
    return await db.get_analytics()


@app.get("/api/clusters")
async def get_clusters():
    """Get all thought clusters with wiki content."""
    clusters = await db.get_all_clusters()
    return {
        "clusters": [
            {
                "id": str(c["id"]),
                "label": c["label"],
                "memberCount": c["member_count"],
                "density": c["density"],
                "velocity7d": c["velocity_7d"],
                "velocity30d": c["velocity_30d"],
                "wikiContent": c["wiki_content"],
                "wikiVersion": c["wiki_version"],
                "trending": c["trending"],
                "createdAt": c["created_at"].isoformat(),
                "updatedAt": c["updated_at"].isoformat(),
            }
            for c in clusters
        ],
    }


@app.get("/api/trends/predictive")
async def get_trends():
    """
    Phase 3: Predictive trend market.
    Returns clusters with accelerating growth velocity.
    """
    trending = await db.get_trending_clusters(limit=20)
    return {
        "trending": [
            {
                "id": str(c["id"]),
                "label": c["label"],
                "memberCount": c["member_count"],
                "velocity7d": c["velocity_7d"],
                "velocity30d": c["velocity_30d"],
                "wikiContent": c["wiki_content"],
                "trending": c["trending"],
            }
            for c in trending
        ],
    }


@app.post("/api/admin/cluster-now")
async def trigger_clustering():
    """Manually trigger clustering (admin/dev endpoint)."""
    await run_clustering()
    return {"status": "clustering complete"}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
