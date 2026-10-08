import { Activity, ArrowUpRight, MessageSquare, Plus, Settings2, ShieldCheck } from 'lucide-react';
import type { Session } from './types';

export type View = 'chat' | 'settings' | 'audit';
interface Props {
  version: string;
  sessions: Session[];
  selectedId: string | null;
  view: View;
  busy: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onView: (view: View) => void;
  onDisconnect: () => void;
}

export function Sidebar({
  version,
  sessions,
  selectedId,
  view,
  busy,
  onNew,
  onSelect,
  onView,
  onDisconnect,
}: Props) {
  return (
    <aside className="sidebar" aria-label="Workspace navigation">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          K
        </div>
        <div>
          <span className="brand-name">KAT</span>
          <span className="brand-subtitle">PERSONAL AI</span>
        </div>
        <span className="version" aria-label="KAT version">
          {version}
        </span>
      </div>
      <button className="new-chat-button" onClick={onNew} disabled={busy}>
        <Plus size={17} /> New conversation{' '}
        <span className="key-hint" aria-hidden="true">
          +
        </span>
      </button>
      <div className="sidebar-label">
        YOUR CONVERSATIONS <span>{sessions.length}</span>
      </div>
      <nav className="session-list" aria-label="Conversations">
        {sessions.length === 0 && <p className="empty-sidebar">Your conversations will appear here.</p>}
        {sessions.map((session) => (
          <button
            key={session.id}
            className={`session-button ${view === 'chat' && selectedId === session.id ? 'selected' : ''}`}
            onClick={() => onSelect(session.id)}
            disabled={busy}
            aria-current={view === 'chat' && selectedId === session.id ? 'page' : undefined}
            title={session.title}
          >
            <MessageSquare size={16} />
            <span>{session.title}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="local-note">
          <ShieldCheck size={17} />
          <div>
            <strong>Kept on your computer</strong>
            <span>History stored on this device.</span>
          </div>
        </div>
        <nav className="utility-nav" aria-label="Tools and settings">
          <button
            className={view === 'audit' ? 'selected' : ''}
            onClick={() => onView('audit')}
            disabled={busy}
            aria-current={view === 'audit' ? 'page' : undefined}
          >
            <Activity size={17} /> Activity & approvals
          </button>
          <button
            className={view === 'settings' ? 'selected' : ''}
            onClick={() => onView('settings')}
            disabled={busy}
            aria-current={view === 'settings' ? 'page' : undefined}
          >
            <Settings2 size={17} /> Settings
          </button>
        </nav>
        <button
          className="connection-row"
          onClick={onDisconnect}
          disabled={busy}
          title="Disconnect from Core"
        >
          <span className="status-dot" /> Local Core connected <ArrowUpRight size={14} />
        </button>
      </div>
    </aside>
  );
}
