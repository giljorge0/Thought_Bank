export default function ResultCard({ result, onIterate }) {
  if (!result) return null;

  const {
    thought, score, density, domain,
    nearestNeighbors = [], nearestClusters = [],
    whatMakesItCommon, whatMakesItNovel, driftSuggestion,
    synthesis, neighborCount,
  } = result;

  const densityColor = {
    SATURATED: '#ef4444',
    DENSE: '#f97316',
    POPULATED: '#eab308',
    SPARSE: '#22c55e',
    FRONTIER: '#3b82f6',
    VOID: '#8b5cf6',
  }[density] || '#888';

  return (
    <div className="result-card">
      {/* Score Header */}
      <div className="score-header">
        <div className="score-number" style={{ color: densityColor }}>
          {score}
        </div>
        <div className="score-meta">
          <span className="density-badge" style={{ background: densityColor }}>
            {density}
          </span>
          <span className="domain-badge">{domain}</span>
        </div>
      </div>

      <p className="thought-echo">"{thought}"</p>

      {/* ── "You Are Not Alone" Synthesis ── */}
      {synthesis && (
        <div className="synthesis-card">
          <div className="synthesis-header">
            <span className="synthesis-icon">◉</span>
            You Are Not Alone
          </div>
          <p className="synthesis-message">{synthesis.message}</p>
          {synthesis.core_insight && (
            <p className="synthesis-insight">
              <strong>Core insight:</strong> {synthesis.core_insight}
            </p>
          )}
          {synthesis.key_themes?.length > 0 && (
            <div className="synthesis-themes">
              {synthesis.key_themes.map((t, i) => (
                <span key={i} className="theme-tag">{t}</span>
              ))}
            </div>
          )}
          {synthesis.best_framing && (
            <p className="synthesis-framing">
              <em>"{synthesis.best_framing}"</em>
            </p>
          )}
        </div>
      )}

      {/* Nearest Neighbors */}
      {nearestNeighbors.length > 0 && (
        <div className="neighbors-section">
          <h4>Nearest Thoughts</h4>
          {nearestNeighbors.map((n, i) => (
            <div key={i} className="neighbor-row">
              <span className="sim-badge">{n.similarity}%</span>
              <span className="neighbor-text">{n.thought}</span>
            </div>
          ))}
        </div>
      )}

      {/* Drift Analysis */}
      <div className="drift-section">
        {nearestClusters.length > 0 && (
          <div className="cluster-tags">
            {nearestClusters.map((c, i) => (
              <span key={i} className="cluster-tag">{c}</span>
            ))}
          </div>
        )}
        {whatMakesItCommon && (
          <p className="drift-line"><strong>Common:</strong> {whatMakesItCommon}</p>
        )}
        {whatMakesItNovel && (
          <p className="drift-line"><strong>Novel:</strong> {whatMakesItNovel}</p>
        )}
        {driftSuggestion && (
          <div className="drift-action">
            <p className="drift-line"><strong>Drift →</strong> {driftSuggestion}</p>
            <button className="iterate-btn" onClick={() => onIterate(driftSuggestion)}>
              Iterate →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
