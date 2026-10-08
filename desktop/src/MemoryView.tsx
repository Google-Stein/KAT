import { useEffect, useState } from 'react';
import { BookOpen, Plus, Search } from 'lucide-react';
import { CoreApi, errorMessage } from './api';
import { MemoryEditor } from './MemoryEditor';
import { FORGET_NOTICE, KIND_LABELS, MEMORY_NOTICE } from './memory-labels';
import type { MemoryFilter, MemoryRecord, MemoryUsage, Project } from './memory-types';

interface Props {
  api: CoreApi;
  enabled: boolean;
  projects: Project[];
  onToggle: (enabled: boolean) => Promise<void>;
  onProject: (project: Project) => void;
  onSource: (sessionId: string, messageId?: string) => void;
}
const date = (value: string | null) => (value ? new Date(value).toLocaleString() : 'Not set');

export function MemoryView({ api, enabled, projects, onToggle, onProject, onSource }: Props) {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [filter, setFilter] = useState<MemoryFilter>({ status: 'confirmed' });
  const [selected, setSelected] = useState<MemoryRecord | null>(null);
  const [revisions, setRevisions] = useState<MemoryRecord[]>([]);
  const [usage, setUsage] = useState<MemoryUsage[]>([]);
  const [editor, setEditor] = useState<'add' | 'edit' | null>(null);
  const [forgetting, setForgetting] = useState(false);
  const [replacement, setReplacement] = useState('');
  const [replacementOptions, setReplacementOptions] = useState<MemoryRecord[]>([]);
  const [projectName, setProjectName] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const timeout = setTimeout(() => {
      void api
        .memories(filter, controller.signal)
        .then(setRecords)
        .catch((failure: unknown) => {
          if (!controller.signal.aborted) setError(errorMessage(failure));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 180);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [api, filter, refresh]);

  useEffect(() => {
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
    setBusy(true);
    setError(null);
    try {
      await action();
      setRefresh((r) => r + 1);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  function updateFilter(next: MemoryFilter) {
    setFilter({ ...next, offset: 0 });
    setSelected(null);
    setForgetting(false);
  }

  return (
    <main className="content-view memory-view">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">WORKSPACE / YOUR CONTEXT</span>
          <h1>Memory</h1>
        </div>
        <button className="primary-button" onClick={() => setEditor('add')} disabled={busy}>
          <Plus size={16} /> Add memory
        </button>
      </header>
      <section className="memory-policy">
        <div>
          <h2>Remember by choice</h2>
          <p>
            Keep facts, preferences and project context across conversations. Nothing is saved automatically.
          </p>
        </div>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={enabled}
            disabled={busy}
            onChange={(e) => {
              const checked = e.target.checked;
              void act(() => onToggle(checked));
            }}
          />
          Enable local memory retrieval
        </label>
        <p className="field-hint" role="status">
          {enabled
            ? 'On · Relevant memory can be used with local models.'
            : 'Off · Memories stay stored and can be managed, but are never inserted into model context.'}
        </p>
        <p className="privacy-note">
          {MEMORY_NOTICE} OpenAI receives no memory records. Ordinary cloud conversation history may contain
          the same information.
        </p>
      </section>
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <div className="memory-filters">
        <label className="memory-search">
          <Search size={16} />
          <input
            aria-label="Search memories"
            placeholder="Search your memories…"
            value={filter.q ?? ''}
            onChange={(e) => updateFilter({ ...filter, q: e.target.value })}
          />
        </label>
        <select
          aria-label="Filter memory kind"
          value={filter.kind ?? ''}
          onChange={(e) =>
            updateFilter({ ...filter, kind: (e.target.value as MemoryFilter['kind']) || undefined })
          }
        >
          <option value="">All kinds</option>
          {Object.entries(KIND_LABELS).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter memory scope"
          value={filter.project_id ?? filter.scope ?? ''}
          onChange={(e) =>
            updateFilter({
              ...filter,
              scope:
                e.target.value === '' ? undefined : e.target.value === 'personal' ? 'personal' : 'project',
              project_id: !['', 'personal'].includes(e.target.value) ? e.target.value : undefined,
            })
          }
        >
          <option value="">All scopes</option>
          <option value="personal">Personal</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter memory status"
          value={filter.status ?? ''}
          onChange={(e) =>
            updateFilter({ ...filter, status: (e.target.value as MemoryFilter['status']) || undefined })
          }
        >
          <option value="">All statuses</option>
          <option value="confirmed">Current</option>
          <option value="superseded">Superseded</option>
          <option value="disputed">Needs review</option>
          <option value="expired">Outdated / expired</option>
        </select>
      </div>
      <div className="memory-layout">
        <section className="memory-list" aria-label="Saved memories" aria-busy={loading}>
          {loading ? (
            <p className="field-hint">Loading memories…</p>
          ) : records.length === 0 ? (
            <div className="memory-empty">
              <BookOpen size={25} />
              <h2>A little context, chosen by you.</h2>
              <p>No memories match this view. Add one here or choose Remember in a conversation.</p>
            </div>
          ) : (
            records.map((record) => (
              <button
                key={record.id}
                className={`memory-item ${selected?.id === record.id ? 'selected' : ''}`}
                aria-label={`Inspect memory: ${record.content}`}
                onClick={() => {
                  setSelected(record);
                  setForgetting(false);
                }}
              >
                <span className="eyebrow">
                  {KIND_LABELS[record.kind]} ·{' '}
                  {record.scope === 'personal'
                    ? 'Personal'
                    : (projects.find((p) => p.id === record.project_id)?.name ?? 'Project')}
                  {record.pinned ? ' · Pinned' : ''}
                </span>
                <span>{record.content}</span>
                <small>
                  {record.status} · revision {record.revision}
                </small>
              </button>
            ))
          )}
          <div className="memory-actions">
            <button
              disabled={loading || !(filter.offset ?? 0)}
              onClick={() => setFilter({ ...filter, offset: Math.max(0, (filter.offset ?? 0) - 100) })}
            >
              Previous
            </button>
            <span className="field-hint">
              {records.length ? `${(filter.offset ?? 0) + 1}–${(filter.offset ?? 0) + records.length}` : '0'}{' '}
              in this view
            </span>
            <button
              disabled={loading || records.length < 100}
              onClick={() => setFilter({ ...filter, offset: (filter.offset ?? 0) + 100 })}
            >
              Next
            </button>
          </div>
        </section>
        <aside className="memory-detail" aria-label="Memory details">
          {selected ? (
            <>
              <span className="eyebrow">
                {selected.status} · REVISION {selected.revision}
              </span>
              <h2>{KIND_LABELS[selected.kind]}</h2>
              <p className="memory-wording">{selected.content}</p>
              <div className="memory-actions">
                <button onClick={() => setEditor('edit')} disabled={busy}>
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
                      setSelected(
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
                        setSelected(
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
                        setSelected(await api.memoryStatus(selected.id, 'disputed', selected.revision)),
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
                    onClick={() =>
                      onSource(selected.source_session_id!, selected.source_message_id ?? undefined)
                    }
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
                    The old record stays inspectable but stops being retrieved. Create the replacement first,
                    in the same scope.
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
                        setSelected(await api.supersedeMemory(selected.id, replacement, selected.revision)),
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
                            setSelected(null);
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
      </div>
      <details className="memory-projects">
        <summary>Project scopes</summary>
        <p className="field-hint">
          Each project has a stable scope. Select it in a conversation to make its relevant memories eligible.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              onProject(await api.createProject(projectName.trim()));
              setProjectName('');
            });
          }}
        >
          <label htmlFor="project-name">New project name</label>
          <input
            id="project-name"
            maxLength={80}
            required
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
          />
          <button disabled={busy || !projectName.trim()}>Create project scope</button>
        </form>
      </details>
      {editor && (
        <MemoryEditor
          projects={projects}
          initial={editor === 'edit' ? (selected ?? undefined) : undefined}
          onClose={() => setEditor(null)}
          onSave={async (fields) => {
            const record =
              editor === 'edit' && selected
                ? await api.editMemory(selected.id, fields, selected.revision)
                : await api.createMemory({
                    ...fields,
                    confirmed: true,
                    origin: 'owner_explicit',
                    source_session_id: null,
                    source_message_id: null,
                  });
            setSelected(record);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </main>
  );
}
