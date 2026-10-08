import { useEffect, useState } from 'react';
import { BookOpen } from 'lucide-react';
import { CoreApi, errorMessage } from './api';
import { FORGET_NOTICE, KIND_LABELS, memoryStatusLabel } from './memory-labels';
import type { MemoryRecord, MemoryUsage } from './memory-types';

interface Props {
  api: CoreApi;
  selected: MemoryRecord | null;
  busy: boolean;
  onBusy: (busy: boolean) => void;
  onChange: (record: MemoryRecord) => void;
  onEdit: () => void;
  onSource: (sessionId: string, messageId?: string) => void;
  onRefresh: () => void;
  onForgotten: () => void;
}
const date = (value: string | null) => (value ? new Date(value).toLocaleString() : 'Not set');

export function MemoryDetail({
  api,
  selected,
  busy,
  onBusy,
  onChange,
  onEdit,
  onSource,
  onRefresh,
  onForgotten,
}: Props) {
  const [revisions, setRevisions] = useState<MemoryRecord[]>([]);
  const [usage, setUsage] = useState<MemoryUsage[]>([]);
  const [forgetting, setForgetting] = useState(false);
  const [replacement, setReplacement] = useState('');
  const [replacementOptions, setReplacementOptions] = useState<MemoryRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setForgetting(false);
    if (!selected) return;
    const controller = new AbortController();
    setRevisions([]);
    setUsage([]);
    setReplacement('');
    setReplacementOptions([]);
    void Promise.all([
      api.memoryRevisions(selected.id, controller.signal),
      api.memoryUsage(selected.id, controller.signal),
      api.memories(
        { status: 'confirmed', scope: selected.scope, project_id: selected.project_id ?? undefined },
        controller.signal,
      ),
    ])
      .then(([versions, uses, alternatives]) => {
        setRevisions(versions);
        setUsage(uses);
        setReplacementOptions(alternatives.filter((r) => r.id !== selected.id));
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      });
    return () => controller.abort();
  }, [api, selected]);

  async function act(action: () => Promise<unknown>) {
    if (busy) return;
    onBusy(true);
    setError(null);
    try {
      await action();
      onRefresh();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      onBusy(false);
    }
  }
  return (
    <aside className="memory-detail" aria-label="Memory details">
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      {selected ? (
        <>
          <span className="eyebrow">
            {memoryStatusLabel(selected)} · REVISION {selected.revision}
          </span>
          <h2>{KIND_LABELS[selected.kind]}</h2>
          <p className="memory-wording">{selected.content}</p>
          <div className="memory-actions">
            <button onClick={() => onEdit()} disabled={busy}>
              Edit memory
            </button>
            <button
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  const {
                    kind,
                    content,
                    scope,
                    project_id,
                    sensitivity,
                    importance,
                    effective_at,
                    expires_at,
                  } = selected;
                  onChange(
                    await api.editMemory(
                      selected.id,
                      {
                        kind,
                        content,
                        scope,
                        project_id,
                        sensitivity,
                        importance,
                        effective_at,
                        expires_at,
                        pinned: !selected.pinned,
                      },
                      selected.revision,
                    ),
                  );
                })
              }
            >
              {selected.pinned ? 'Unpin' : 'Pin'}
            </button>
            {selected.status !== 'superseded' && (
              <button
                disabled={busy}
                onClick={() =>
                  void act(async () =>
                    onChange(
                      await api.memoryStatus(
                        selected.id,
                        selected.status === 'confirmed' ? 'expired' : 'confirmed',
                        selected.revision,
                      ),
                    ),
                  )
                }
              >
                {selected.status === 'confirmed' ? 'Mark outdated' : 'Confirm after review'}
              </button>
            )}
            {selected.status === 'confirmed' && (
              <button
                disabled={busy}
                onClick={() =>
                  void act(async () =>
                    onChange(await api.memoryStatus(selected.id, 'disputed', selected.revision)),
                  )
                }
              >
                Needs review
              </button>
            )}
          </div>
          <h3>Why KAT has this</h3>
          <p>
            {selected.origin === 'owner_explicit'
              ? 'Entered and confirmed by you in Memory.'
              : `You explicitly selected a ${selected.source_role ?? 'conversation'} message and reviewed this wording.`}
          </p>
          {selected.source_session_id &&
            (selected.source_available ? (
              <button
                onClick={() => onSource(selected.source_session_id!, selected.source_message_id ?? undefined)}
              >
                View source conversation
              </button>
            ) : (
              <p className="field-hint">
                The original source is unavailable. No replacement evidence was created.
              </p>
            ))}
          {selected.superseded_by && (
            <p className="field-hint">Superseded by memory {selected.superseded_by}.</p>
          )}
          <dl className="memory-dates">
            <dt>Created</dt>
            <dd>{date(selected.created_at)}</dd>
            <dt>Updated</dt>
            <dd>{date(selected.updated_at)}</dd>
            <dt>Reviewed</dt>
            <dd>{date(selected.last_reviewed_at)}</dd>
            <dt>Effective</dt>
            <dd>{date(selected.effective_at)}</dd>
            <dt>Expires</dt>
            <dd>{date(selected.expires_at)}</dd>
          </dl>
          <details>
            <summary>Revision history · {revisions.length}</summary>
            {revisions.map((r) => (
              <div className="memory-revision" key={r.revision}>
                <strong>
                  Revision {r.revision} · {r.status}
                </strong>
                <small>{date(r.updated_at)}</small>
                <p>{r.content}</p>
              </div>
            ))}
          </details>
          <details>
            <summary>Where used · {usage.length}</summary>
            {usage.length === 0 ? (
              <p className="field-hint">No successful local response has used this memory.</p>
            ) : (
              usage.map((u) => (
                <div className="memory-revision" key={u.assistant_message_id}>
                  <button onClick={() => onSource(u.session_id, u.assistant_message_id)}>
                    View response · revision {u.revision}
                  </button>
                  <small>{date(u.used_at)} · local</small>
                </div>
              ))
            )}
          </details>
          {selected.status !== 'superseded' && (
            <details>
              <summary>Supersede with a reviewed replacement</summary>
              <p className="field-hint">
                The old record stays inspectable but stops being retrieved. Create the replacement first, in
                the same scope.
              </p>
              <select
                aria-label="Replacement memory"
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
              >
                <option value="">Choose a current memory</option>
                {replacementOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.content.slice(0, 100)}
                  </option>
                ))}
              </select>
              <button
                disabled={busy || !replacement}
                onClick={() =>
                  void act(async () =>
                    onChange(await api.supersedeMemory(selected.id, replacement, selected.revision)),
                  )
                }
              >
                Confirm supersession
              </button>
            </details>
          )}
          <div className="forget-panel">
            <button disabled={busy} onClick={() => setForgetting(true)}>
              Forget memory
            </button>
            {forgetting && (
              <>
                <p>{FORGET_NOTICE}</p>
                <p>
                  Current wording, revisions and search entries will be removed. Usage and audit keep
                  identifiers only.
                </p>
                <div className="memory-actions">
                  <button onClick={() => setForgetting(false)} disabled={busy}>
                    Keep memory
                  </button>
                  <button
                    className="danger-button"
                    disabled={busy}
                    onClick={() =>
                      void act(async () => {
                        await api.forgetMemory(selected.id);
                        onForgotten();
                        setForgetting(false);
                      })
                    }
                  >
                    Confirm forget
                  </button>
                </div>
              </>
            )}
          </div>
        </>
      ) : (
        <div className="memory-empty">
          <BookOpen size={24} />
          <p>Select a memory to inspect its source, revisions and use.</p>
        </div>
      )}
    </aside>
  );
}
