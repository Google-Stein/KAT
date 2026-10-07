import { useState } from 'react';
import { ArrowRight, LockKeyhole, RefreshCw, ShieldCheck } from 'lucide-react';
import type { CoreConnection } from './types';

interface Props {
  native: boolean;
  connecting: boolean;
  error: string | null;
  onConnect: (connection?: CoreConnection, restart?: boolean) => Promise<void>;
}

export function ConnectScreen({ native, connecting, error, onConnect }: Props) {
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:42800');
  const [token, setToken] = useState('');
  return (
    <main className="connect-page">
      <div className="connect-card">
        <div className="brand-mark large" aria-hidden="true">
          K
        </div>
        <span className="eyebrow">YOUR PERSONAL AI WORKSPACE</span>
        <h1>Welcome to KAT.</h1>
        <p className="muted">
          A little more clarity. A little more possibility.
          <br />
          Your conversations, on your computer.
        </p>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        {native ? (
          <button
            className="primary-button connect-button"
            onClick={() => void onConnect(undefined, true)}
            disabled={connecting}
          >
            <RefreshCw size={17} className={connecting ? 'spin' : ''} />
            {connecting ? 'Starting your local Core…' : 'Retry local connection'}
          </button>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void onConnect({ base_url: baseUrl, token });
            }}
          >
            <p className="developer-note">Browser development connection</p>
            <label htmlFor="core-url">Local Core URL</label>
            <input
              id="core-url"
              type="url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              required
              disabled={connecting}
              autoComplete="off"
            />
            <label htmlFor="core-token">Core access token</label>
            <input
              id="core-token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              required
              disabled={connecting}
              autoComplete="off"
              spellCheck={false}
            />
            <p className="field-hint">
              <LockKeyhole size={13} /> Kept in memory for this connection only.
            </p>
            <button className="primary-button connect-button" disabled={connecting} type="submit">
              {connecting ? 'Connecting…' : 'Connect to KAT'} <ArrowRight size={17} />
            </button>
          </form>
        )}
        <div className="connect-footer">
          <ShieldCheck size={15} /> Local storage · Actions with your permission
        </div>
      </div>
    </main>
  );
}
