import { useEffect, useRef } from 'react';
import { ArrowUp, Clock3, MessageSquare, Sparkles, Terminal, UserRound } from 'lucide-react';
import { ApprovalCard } from './ApprovalCard';
import type { Approval, Message, Session, Settings } from './types';

interface Props {
  provider: Settings['provider'] | undefined;
  session: Session | undefined;
  messages: Message[];
  approvals: Approval[];
  draft: string;
  busy: boolean;
  loading: boolean;
  providerReady: boolean;
  onDraft: (draft: string) => void;
  onSend: () => void;
  onDecision: (id: string, approved: boolean) => void;
  onSettings: () => void;
}

export function ChatView({
  provider,
  session,
  messages,
  approvals,
  draft,
  busy,
  loading,
  providerReady,
  onDraft,
  onSend,
  onDecision,
  onSettings,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pending = approvals.filter((approval) => approval.status === 'pending');
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages, approvals, busy]);
  useEffect(() => {
    if (!busy) inputRef.current?.focus();
  }, [busy, session?.id]);
  return (
    <main className="chat-view">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">WORKSPACE / CONVERSATION</span>
          <h1>{session?.title ?? 'Your next idea starts here'}</h1>
        </div>
        <span className="local-pill" aria-label="Selected inference provider">
          {provider === 'ollama'
            ? 'Ollama · local'
            : provider === 'openai'
              ? 'OpenAI · cloud'
              : 'Loading provider…'}
        </span>
      </header>
      {!providerReady && (
        <div className="provider-banner">
          <span>Configure a local model or save an OpenAI API key in Settings to start chatting.</span>
          <button onClick={onSettings}>View settings</button>
        </div>
      )}
      <div
        className="transcript"
        role="log"
        aria-label="Conversation messages"
        aria-live="polite"
        aria-busy={loading || busy}
      >
        {loading ? (
          <div className="loading-state">
            <span className="pulse-dot" /> Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <div className="welcome">
            <div className="welcome-symbol">
              <Sparkles size={28} strokeWidth={1.5} />
            </div>
            <span className="eyebrow">A SPACE TO THINK TOGETHER</span>
            <h2>Hello. I’m KAT.</h2>
            <p>
              Let’s turn a question into a conversation.
              <br />
              Start small. See where it takes us.
            </p>
            <div className="suggestions">
              <button
                disabled={busy || !providerReady}
                onClick={() => onDraft('Help me think through an idea.')}
              >
                <MessageSquare size={18} />
                <span>
                  Think something through<small>A fresh perspective on your idea</small>
                </span>
              </button>
              <button
                disabled={busy || !providerReady}
                onClick={() => onDraft('What is the current local time?')}
              >
                <Clock3 size={18} />
                <span>
                  Check the time<small>Try a simple local tool</small>
                </span>
              </button>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <article
              key={message.id}
              className={`message ${message.role}`}
              aria-label={`${message.role} message`}
            >
              <div className={`message-avatar ${message.role}`} aria-hidden="true">
                {message.role === 'assistant' ? (
                  'K'
                ) : message.role === 'user' ? (
                  <UserRound size={17} />
                ) : (
                  <Terminal size={16} />
                )}
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <strong>
                    {message.role === 'assistant' ? 'KAT' : message.role === 'user' ? 'You' : 'Tool result'}
                  </strong>
                  <time dateTime={message.created_at}>
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </time>
                </div>
                <div className="message-content">{message.content}</div>
              </div>
            </article>
          ))
        )}
        {pending.map((approval) => (
          <ApprovalCard key={approval.id} approval={approval} busy={busy} onDecision={onDecision} />
        ))}
        {busy && (
          <div className="thinking" role="status">
            <div className="message-avatar assistant">K</div>
            <span className="thinking-dots">
              <i />
              <i />
              <i />
            </span>
            <span>KAT is working…</span>
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="composer-wrap">
        {pending.length > 0 && (
          <p className="composer-note">Review the pending tool requests above before continuing.</p>
        )}
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            onSend();
          }}
        >
          <label className="sr-only" htmlFor="message-input">
            Message KAT
          </label>
          <textarea
            id="message-input"
            ref={inputRef}
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            placeholder="Message KAT…"
            maxLength={20000}
            rows={2}
            disabled={busy || loading || !providerReady || pending.length > 0}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                if (draft.trim()) onSend();
              }
            }}
          />
          <button
            type="submit"
            className="send-button"
            disabled={busy || loading || !providerReady || pending.length > 0 || !draft.trim()}
            aria-label="Send message"
          >
            <ArrowUp size={20} />
          </button>
        </form>
        <div className="composer-footer">
          <span>KAT can make mistakes. Review important information.</span>
          <span>Enter to send · Shift + Enter for a new line</span>
        </div>
      </div>
    </main>
  );
}
