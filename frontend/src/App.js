import { useState } from 'react';

function App() {
  const [promptArea, setPromptArea] = useState('');
  const [promptResponse, setPromptResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async () => {
    const url = 'http://localhost:4444/api/prompt';
    let tmpPromptResponse = '';

    // reset UI states for a fresh submit
    setPromptResponse('');
    setErrorMsg('');
    setLoading(true);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptArea }),
      });

      // If backend denied the request (we expect JSON {ok:false, message:...} with 403)
      if (!response.ok) {
        // try parse JSON message, fallback to text
        let msg = "Data can't be shown.";
        try {
          const j = await response.json();
          if (j && j.message) msg = j.message;
        } catch (e) {
          try {
            const t = await response.text();
            if (t) msg = t;
          } catch (e2) {
            // ignore
          }
        }

        setErrorMsg(msg);
        setPromptResponse(msg); // show refusal in same area if you prefer
        setLoading(false);
        return;
      }

      // OK: proceed to stream the body
      if (!response.body) {
        setErrorMsg("No response body from server.");
        setLoading(false);
        return;
      }

      // Use TextDecoderStream to convert bytes to string chunks
      // Note: TextDecoderStream may not exist in some older browsers.
      // eslint-disable-next-line no-undef
      const decoder = new TextDecoderStream();
      const reader = response.body.pipeThrough(decoder).getReader();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value) {
          tmpPromptResponse += value;
          setPromptResponse(tmpPromptResponse);
        }
      }

    } catch (error) {
      console.error("Fetch/stream error:", error);
      setErrorMsg("An error occurred. Check console for details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'row', justifyContent: 'center' }}>
      <div style={{ order: 1, width: '80vh' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ order: -1 }}>Hello World!</h2>
          <textarea
            rows={10}
            onChange={(e) => setPromptArea(e.target.value)}
            style={{ order: 2, marginBottom: '1rem' }}
            value={promptArea}
          ></textarea>

          <div style={{ order: 3 }}>
            <button onClick={handleSubmit} disabled={loading}>
              {loading ? 'Loading…' : 'Submit'}
            </button>{' '}
            <button
              onClick={() => {
                setPromptArea('');
                setPromptResponse('');
                setErrorMsg('');
              }}
              disabled={loading}
            >
              Clear
            </button>
          </div>

          <div style={{ order: 4, marginTop: '1rem' }}>
            <h3>Streamed Prompt Response:</h3>
            {errorMsg ? (
              <div style={{ color: 'crimson' }}>{errorMsg}</div>
            ) : (
              <pre style={{ whiteSpace: 'pre-wrap' }}>{promptResponse}</pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
