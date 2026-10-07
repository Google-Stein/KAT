import { Activity, RefreshCw } from 'lucide-react';
import type { AuditEvent } from './types';

interface Props {
  events: AuditEvent[];
  loading: boolean;
  onRefresh: () => void;
}

export function AuditView({ events, loading, onRefresh }: Props) {
  return (
    <main className="content-view">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">WORKSPACE / TRANSPARENCY</span>
          <h1>Activity & approvals</h1>
        </div>
        <button className="secondary-button" onClick={onRefresh} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </header>
      <div className="audit-content">
        <p className="page-intro">A record of tool requests, your decisions, and what happened next.</p>
        <div className="audit-summary">
          <Activity size={19} />
          <span>Latest 100 events</span>
          <span className="local-pill">Stored locally</span>
        </div>
        {loading ? (
          <p role="status" className="muted">
            Loading activity…
          </p>
        ) : events.length === 0 ? (
          <div className="empty-activity">
            <ShieldIllustration />
            <h2>Nothing to review yet</h2>
            <p>When KAT requests a tool, its activity appears here.</p>
          </div>
        ) : (
          <div className="audit-list">
            {events.map((event) => (
              <article key={event.id} className={`audit-event ${event.error ? 'has-error' : ''}`}>
                <span className="audit-dot" />
                <div>
                  <div className="audit-event-heading">
                    <strong>{event.event.replaceAll('_', ' ')}</strong>
                    <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time>
                  </div>
                  {event.tool_name && <code className="tool-name">{event.tool_name}</code>}
                  {event.error && <p className="audit-error">{event.error}</p>}
                  <details>
                    <summary>View event details</summary>
                    <pre>
                      {JSON.stringify(
                        { session_id: event.session_id, approval_id: event.approval_id, ...event.details },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function ShieldIllustration() {
  return (
    <div className="welcome-symbol">
      <Activity size={28} strokeWidth={1.5} />
    </div>
  );
}
