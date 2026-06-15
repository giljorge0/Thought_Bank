import { useState, useEffect, useCallback } from 'react';
import ThoughtInput from './components/ThoughtInput';
import ResultCard from './components/ResultCard';
import ThoughtMap from './components/ThoughtMap';
import { useWebSocket } from './hooks/useWebSocket';
import { submitThought, fetchMap } from './api/client';
import './app.css';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [mapData, setMapData] = useState([]);
  const [newPing, setNewPing] = useState(null);
  const [driftText, setDriftText] = useState('');
  const [error, setError] = useState(null);
  const [view, setView] = useState('input'); // input | map | trends

  // Load initial map data
  useEffect(() => {
    fetchMap()
      .then((data) => setMapData(data.thoughts || []))
      .catch(() => {});
  }, []);

  // WebSocket for live updates
  const handleWsMessage = useCallback((msg) => {
    if (msg.type === 'NEW_THOUGHT') {
      setMapData((prev) => [msg.payload, ...prev]);
      setNewPing(msg.payload);
    }
  }, []);

  const wsConnected = useWebSocket(handleWsMessage);

  // Submit handler
  const handleSubmit = async (text) => {
    setLoading(true);
    setError(null);
    setDriftText('');
    try {
      const res = await submitThought(text);
      setResult(res);
      setHistory((prev) => [res, ...prev]);
      // Map will update via WebSocket, but add locally too
      setMapData((prev) => [
        {
          id: res.id,
          thought: res.thought,
          score: res.score,
          density: res.density,
          domain: res.domain,
          mapCoordinates: res.mapCoordinates,
          createdAt: res.createdAt,
        },
        ...prev,
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleIterate = (suggestion) => {
    setDriftText(suggestion);
    setView('input');
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Thought Bank</h1>
        <p className="tagline">Dump a thought. See where it lands in the collective mind.</p>
        <nav className="view-nav">
          <button
            className={view === 'input' ? 'active' : ''}
            onClick={() => setView('input')}
          >
            Submit
          </button>
          <button
            className={view === 'map' ? 'active' : ''}
            onClick={() => setView('map')}
          >
            Map ({mapData.length})
          </button>
        </nav>
        <div className={`ws-indicator ${wsConnected ? 'on' : ''}`}>
          {wsConnected ? '● Live' : '○ Connecting...'}
        </div>
      </header>

      <main className="app-main">
        {view === 'input' && (
          <div className="input-view">
            <ThoughtInput
              onSubmit={handleSubmit}
              loading={loading}
              driftSuggestion={driftText}
            />

            {error && <div className="error-banner">{error}</div>}

            {result && (
              <ResultCard result={result} onIterate={handleIterate} />
            )}

            {history.length > 1 && (
              <div className="history-section">
                <h3>Previous Submissions</h3>
                {history.slice(1, 6).map((r) => (
                  <div key={r.id} className="history-card">
                    <div className="history-meta">
                      <span className="history-score">{r.score}</span>
                      <span className="history-density">{r.density}</span>
                      {r.synthesis && <span className="yana-badge">◉ YANA</span>}
                    </div>
                    <p>{r.thought.slice(0, 100)}{r.thought.length > 100 ? '…' : ''}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {view === 'map' && (
          <div className="map-view">
            <ThoughtMap
              thoughts={mapData}
              newPing={newPing}
              colorBy="domain"
            />
          </div>
        )}
      </main>
    </div>
  );
}
