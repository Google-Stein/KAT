import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { AlertCircle, X } from 'lucide-react';
import { CoreApi, errorMessage } from './api';
import { AuditView } from './AuditView';
import { ChatView } from './ChatView';
import { ConnectScreen } from './ConnectScreen';
import { SettingsView } from './SettingsView';
import { Sidebar } from './Sidebar';
import type { View } from './Sidebar';
import type {
  Approval,
  AuditEvent,
  CoreConnection,
  Health,
  Message,
  Session,
  Settings,
  SettingsUpdate,
} from './types';

export default function App() {
  const [native] = useState(() => isTauri());
  const [api, setApi] = useState<CoreApi | null>(null);
  const [connecting, setConnecting] = useState(native);
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [draft, setDraft] = useState('');
  const [view, setView] = useState<View>('chat');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actionRef = useRef(false);
  const connectRef = useRef(false);

  const connect = useCallback(async (connection?: CoreConnection, restart = false) => {
    if (connectRef.current) return;
    connectRef.current = true;
    setConnecting(true);
    setError(null);
    try {
      const resolved =
        connection ?? (await invoke<CoreConnection>(restart ? 'restart_core' : 'core_connection'));
      const client = new CoreApi(resolved);
      const [status, savedSessions, savedSettings] = await Promise.all([
        client.health(),
        client.sessions(),
        client.settings(),
      ]);
      setHealth(status);
      setSessions(savedSessions);
      setSettings(savedSettings);
      setSelectedId(savedSessions[0]?.id ?? null);
      setApi(client);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      connectRef.current = false;
      setConnecting(false);
    }
  }, []);

  useEffect(() => {
    if (native) void connect();
  }, [native, connect]);

  useEffect(() => {
    if (!api || !selectedId || view !== 'chat' || busy) return;
    const controller = new AbortController();
    setLoading(true);
    void Promise.all([
      api.messages(selectedId, controller.signal),
      api.approvals(selectedId, controller.signal),
    ])
      .then(([savedMessages, savedApprovals]) => {
        setMessages(savedMessages);
        setApprovals(savedApprovals);
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, selectedId, view, busy]);

  const refreshAudit = useCallback(async () => {
    if (!api) return;
    setAuditLoading(true);
    try {
      setEvents(await api.audit());
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setAuditLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (view === 'audit') void refreshAudit();
  }, [view, refreshAudit]);

  function selectSession(id: string) {
    if (busy) return;
    if (id !== selectedId) {
      setMessages([]);
      setApprovals([]);
      setDraft('');
    }
    setSelectedId(id);
    setView('chat');
    setError(null);
  }

  async function newSession() {
    if (!api || actionRef.current) return;
    actionRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const session = await api.createSession();
      setSessions((previous) => [session, ...previous]);
      setMessages([]);
      setApprovals([]);
      setDraft('');
      setSelectedId(session.id);
      setView('chat');
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  }

  async function sendMessage() {
    const content = draft.trim();
    if (
      !api ||
      !content ||
      actionRef.current ||
      loading ||
      !health?.provider_ready ||
      approvals.some((approval) => approval.status === 'pending')
    )
      return;
    actionRef.current = true;
    setBusy(true);
    setDraft('');
    setError(null);
    try {
      let sessionId = selectedId;
      if (!sessionId) {
        const session = await api.createSession();
        setSessions((previous) => [session, ...previous]);
        sessionId = session.id;
        setSelectedId(sessionId);
      }
      const optimistic: Message = {
        id: 'sending',
        session_id: sessionId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((previous) => [...previous, optimistic]);
      const response = await api.sendMessage(sessionId, content);
      setMessages((previous) => [
        ...previous.filter((message) => message.id !== 'sending'),
        response.user_message,
        response.assistant_message,
      ]);
      setApprovals(response.approvals);
      try {
        setSessions(await api.sessions());
      } catch (failure) {
        setError(`Your message was saved. ${errorMessage(failure)}`);
      }
    } catch (failure) {
      setMessages((previous) => previous.filter((message) => message.id !== 'sending'));
      setDraft(content);
      setError(errorMessage(failure));
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  }

  async function decide(id: string, approved: boolean) {
    if (!api || actionRef.current) return;
    actionRef.current = true;
    setBusy(true);
    setError(null);
    try {
      await api.decide(id, approved);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  }

  async function saveSettings(update: SettingsUpdate) {
    if (!api || actionRef.current) return;
    actionRef.current = true;
    setBusy(true);
    setSettingsSaved(false);
    setError(null);
    try {
      setSettings(await api.updateSettings(update));
      setHealth(await api.health());
      setSettingsSaved(true);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  }

  function disconnect() {
    setApi(null);
    setHealth(null);
    setSessions([]);
    setSelectedId(null);
    setMessages([]);
    setApprovals([]);
    setSettings(null);
    setEvents([]);
    setDraft('');
    setView('chat');
    setError(null);
    setLoading(false);
    setAuditLoading(false);
  }

  if (!api)
    return <ConnectScreen native={native} connecting={connecting} error={error} onConnect={connect} />;
  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        selectedId={selectedId}
        view={view}
        busy={busy}
        onNew={() => void newSession()}
        onSelect={selectSession}
        onView={(next) => {
          setView(next);
          setSettingsSaved(false);
          setError(null);
        }}
        onDisconnect={disconnect}
      />
      <div className="workspace">
        {error && (
          <div className="error-banner workspace-error" role="alert">
            <AlertCircle size={17} />
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError(null)}>
              <X size={16} />
            </button>
          </div>
        )}
        {view === 'chat' && (
          <ChatView
            session={sessions.find((session) => session.id === selectedId)}
            messages={messages}
            approvals={approvals}
            draft={draft}
            busy={busy}
            loading={loading}
            providerReady={health?.provider_ready ?? false}
            onDraft={setDraft}
            onSend={() => void sendMessage()}
            onDecision={(id, approved) => void decide(id, approved)}
            onSettings={() => setView('settings')}
          />
        )}
        {view === 'settings' && (
          <SettingsView
            settings={settings}
            saving={busy}
            saved={settingsSaved}
            onSave={(update) => void saveSettings(update)}
          />
        )}
        {view === 'audit' && (
          <AuditView events={events} loading={auditLoading} onRefresh={() => void refreshAudit()} />
        )}
      </div>
    </div>
  );
}
