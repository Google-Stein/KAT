import { useEffect, useState } from 'react';
import { BookOpen, Plus, Search } from 'lucide-react';
import { CoreApi, errorMessage } from './api';
import { MemoryEditor } from './MemoryEditor';
import { MemoryDetail } from './MemoryDetail';
import { KIND_LABELS, MEMORY_NOTICE, memoryStatusLabel } from './memory-labels';
import type { MemoryFilter, MemoryRecord, Project } from './memory-types';

interface Props {
  api: CoreApi;
  enabled: boolean;
  projects: Project[];
  onToggle: (enabled: boolean) => Promise<void>;
  onProject: (project: Project) => void;
  onSource: (sessionId: string, messageId?: string) => void;
}

export function MemoryView({ api, enabled, projects, onToggle, onProject, onSource }: Props) {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [filter, setFilter] = useState<MemoryFilter>({ status: 'confirmed' });
  const [selected, setSelected] = useState<MemoryRecord | null>(null);
  const [editor, setEditor] = useState<'add' | 'edit' | null>(null);
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
                  {memoryStatusLabel(record)} · revision {record.revision}
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
        <MemoryDetail
          api={api}
          selected={selected}
          busy={busy}
          onBusy={setBusy}
          onChange={setSelected}
          onEdit={() => setEditor('edit')}
          onSource={onSource}
          onRefresh={() => setRefresh((r) => r + 1)}
          onForgotten={() => setSelected(null)}
        />
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
