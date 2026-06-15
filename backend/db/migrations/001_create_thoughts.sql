-- thought-bank/backend/db/migrations/001_create_thoughts.sql
-- Extends originality_radar's ideas schema for multi-user thought clustering

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Thought Clusters ────────────────────────────────────────────────────────
-- Dense neighborhoods in vector space, detected by DBSCAN or k-NN density.
-- Each cluster gets a living wiki synthesis that updates as new thoughts arrive.

CREATE TABLE IF NOT EXISTS thought_clusters (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  label           TEXT,                       -- LLM-generated cluster name
  centroid        vector(768),                -- average vector of member thoughts
  member_count    INTEGER     DEFAULT 0,
  density         FLOAT       DEFAULT 0,      -- avg pairwise similarity within cluster
  wiki_content    TEXT,                        -- synthesized wiki page (auto_wiki style)
  wiki_version    INTEGER     DEFAULT 0,
  claims          JSONB       DEFAULT '[]',   -- extracted atomic claims (relations.py)
  contradictions  JSONB       DEFAULT '[]',   -- detected contradictions
  related_clusters UUID[]     DEFAULT '{}',
  velocity_7d     FLOAT       DEFAULT 0,      -- cluster growth rate (7-day window)
  velocity_30d    FLOAT       DEFAULT 0,      -- cluster growth rate (30-day window)
  trending        BOOLEAN     DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Thoughts ────────────────────────────────────────────────────────────────
-- Core table. Each row is one raw human thought + its embedding.

CREATE TABLE IF NOT EXISTS thoughts (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  thought         TEXT        NOT NULL,
  vector          vector(768),                -- nomic-embed-text produces 768-dim
  score           INTEGER     DEFAULT 0,      -- originality score (1 - avgSim) * 100
  density         VARCHAR(20) DEFAULT 'POPULATED',
  domain          VARCHAR(32) DEFAULT 'General',
  cluster_id      UUID        REFERENCES thought_clusters(id) ON DELETE SET NULL,

  -- k-NN results cached at insertion time
  nearest_neighbors JSONB     DEFAULT '[]',
  neighbor_count    INTEGER   DEFAULT 0,      -- how many thoughts within sim >= 0.75

  -- Synthesis result ("You Are Not Alone" response)
  synthesis       JSONB       DEFAULT NULL,   -- {message, shared_count, core_insight}

  -- 2D map coordinates (PCA projection)
  map_x           FLOAT       DEFAULT 0,
  map_y           FLOAT       DEFAULT 0,

  -- LLM narrative (drift analysis, ported from originality_radar)
  nearest_clusters    TEXT[]   DEFAULT '{}',
  what_makes_it_common TEXT,
  what_makes_it_novel  TEXT,
  drift_suggestion     TEXT,

  -- Metadata
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  ip_hash         VARCHAR(64),
  user_agent      TEXT
);

-- ── Indexes ─────────────────────────────────────────────────────────────────

-- HNSW for fast approximate k-NN (cosine distance)
CREATE INDEX IF NOT EXISTS thoughts_vector_hnsw_idx
  ON thoughts USING hnsw (vector vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS thoughts_density_idx    ON thoughts (density);
CREATE INDEX IF NOT EXISTS thoughts_created_at_idx ON thoughts (created_at DESC);
CREATE INDEX IF NOT EXISTS thoughts_score_idx      ON thoughts (score DESC);
CREATE INDEX IF NOT EXISTS thoughts_cluster_idx    ON thoughts (cluster_id);
CREATE INDEX IF NOT EXISTS thoughts_domain_idx     ON thoughts (domain);
CREATE INDEX IF NOT EXISTS thoughts_ip_hash_idx    ON thoughts (ip_hash, created_at DESC);

-- Cluster centroid search
CREATE INDEX IF NOT EXISTS clusters_centroid_hnsw_idx
  ON thought_clusters USING hnsw (centroid vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS clusters_trending_idx ON thought_clusters (trending, velocity_7d DESC);

-- ── Analytics ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS thought_analytics (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  total_thoughts       INTEGER DEFAULT 0,
  avg_score            FLOAT   DEFAULT 0,
  saturation_percent   FLOAT   DEFAULT 0,
  frontier_percent     FLOAT   DEFAULT 0,
  total_clusters       INTEGER DEFAULT 0,
  trending_clusters    INTEGER DEFAULT 0,
  last_updated         TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION update_thought_analytics()
RETURNS void AS $$
BEGIN
  DELETE FROM thought_analytics;
  INSERT INTO thought_analytics (
    total_thoughts, avg_score, saturation_percent, frontier_percent,
    total_clusters, trending_clusters, last_updated
  )
  SELECT
    COUNT(*),
    COALESCE(AVG(score), 0),
    COALESCE(
      COUNT(*) FILTER (WHERE density IN ('SATURATED', 'DENSE')) * 100.0
      / NULLIF(COUNT(*), 0), 0
    ),
    COALESCE(
      COUNT(*) FILTER (WHERE density IN ('FRONTIER', 'VOID')) * 100.0
      / NULLIF(COUNT(*), 0), 0
    ),
    (SELECT COUNT(*) FROM thought_clusters),
    (SELECT COUNT(*) FROM thought_clusters WHERE trending = TRUE),
    NOW()
  FROM thoughts;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trigger_update_thought_analytics()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM update_thought_analytics();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS thoughts_analytics_trigger ON thoughts;
CREATE TRIGGER thoughts_analytics_trigger
  AFTER INSERT ON thoughts
  FOR EACH STATEMENT
  EXECUTE FUNCTION trigger_update_thought_analytics();

SELECT update_thought_analytics();
