import { useState } from 'react';

export default function ThoughtInput({ onSubmit, loading, driftSuggestion }) {
  const [text, setText] = useState(driftSuggestion || '');

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onSubmit(trimmed);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // If driftSuggestion changed, populate
  if (driftSuggestion && !text) {
    setText(driftSuggestion);
  }

  return (
    <div className="thought-input">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Drop a thought. Any thought. No filter needed."
        rows={3}
        maxLength={2000}
        disabled={loading}
      />
      <div className="input-footer">
        <span className="char-count">{text.length}/2000</span>
        <button onClick={handleSubmit} disabled={loading || !text.trim()}>
          {loading ? 'Thinking...' : 'Submit →'}
        </button>
      </div>
    </div>
  );
}
