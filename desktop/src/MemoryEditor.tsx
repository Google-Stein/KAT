import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import type { MemoryFields, MemoryKind, MemoryRecord, Project } from './memory-types';

import { KIND_LABELS, MEMORY_NOTICE } from './memory-labels';

interface Props {
  projects: Project[];
  initial?: MemoryRecord;
  text?: string;
  projectId?: string | null;
  source?: boolean;
  onSave: (fields: MemoryFields) => Promise<void>;
  onClose: () => void;
}

export function MemoryEditor({ projects, initial, text = '', projectId, source, onSave, onClose }: Props) {
  const [content, setContent] = useState(initial?.content ?? text.slice(0, 2000));
  const [kind, setKind] = useState<MemoryKind>(initial?.kind ?? 'semantic');
  const [scope, setScope] = useState(initial?.project_id ?? projectId ?? 'personal');
  const [pinned, setPinned] = useState(initial?.pinned ?? false);
  const [importance, setImportance] = useState(initial?.importance ?? 0);
  const [expires, setExpires] = useState(initial?.expires_at?.slice(0, 10) ?? '');
  const [effective, setEffective] = useState(initial?.effective_at?.slice(0, 10) ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    return () => {
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop">
      <section
        ref={dialogRef}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && !saving) {
            event.preventDefault();
            onClose();
          }
          if (event.key !== 'Tab') return;
          const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled)',
          );
          if (!controls?.length) return;
          const first = controls[0],
            last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
        className="memory-editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="memory-editor-title"
      >
        <header>
          <div>
            <span className="eyebrow">EXPLICIT OWNER REVIEW</span>
            <h2 id="memory-editor-title">
              {initial ? 'Edit memory' : source ? 'Remember this message' : 'Add memory'}
            </h2>
          </div>
          <button aria-label="Close memory review" onClick={onClose} disabled={saving}>
            <X size={18} />
          </button>
        </header>
        <p className="field-hint">
          Review the wording and scope before saving. No model call is needed. Goals and working preferences
          never authorize actions.
        </p>
        {text.length > 2000 && !initial && (
          <p role="status">
            This message is longer than a memory. Review the first 2,000 characters or replace them with a
            short statement.
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (saving) return;
            setSaving(true);
            setError(null);
            void onSave({
              content: content.trim(),
              kind,
              scope: scope === 'personal' ? 'personal' : 'project',
              project_id: scope === 'personal' ? null : scope,
              sensitivity: 'normal',
              pinned,
              importance,
              effective_at: effective
                ? initial?.effective_at?.startsWith(effective)
                  ? initial.effective_at
                  : `${effective}T00:00:00+00:00`
                : null,
              expires_at: expires
                ? initial?.expires_at?.startsWith(expires)
                  ? initial.expires_at
                  : `${expires}T23:59:59+00:00`
                : null,
            })
              .then(onClose)
              .catch((failure: unknown) =>
                setError(failure instanceof Error ? failure.message : 'Memory could not be saved.'),
              )
              .finally(() => setSaving(false));
          }}
        >
          <label htmlFor="memory-wording">Memory wording</label>
          <textarea
            id="memory-wording"
            autoFocus
            rows={5}
            maxLength={2000}
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={saving}
          />
          <div className="memory-form-grid">
            <div>
              <label htmlFor="memory-kind">Kind</label>
              <select
                id="memory-kind"
                value={kind}
                onChange={(e) => setKind(e.target.value as MemoryKind)}
                disabled={saving}
              >
                {Object.entries(KIND_LABELS).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="memory-scope">Scope</label>
              <select
                id="memory-scope"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                disabled={saving || !!initial}
              >
                <option value="personal">Personal</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="memory-effective">Effective from (UTC date)</label>
              <input
                id="memory-effective"
                type="date"
                value={effective}
                onChange={(e) => setEffective(e.target.value)}
                disabled={saving}
              />
            </div>
            <div>
              <label htmlFor="memory-expiry">Expires after (UTC date)</label>
              <input
                id="memory-expiry"
                type="date"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
                disabled={saving}
              />
            </div>
            <div>
              <label htmlFor="memory-importance">Importance</label>
              <select
                id="memory-importance"
                value={importance}
                onChange={(e) => setImportance(Number(e.target.value))}
                disabled={saving}
              >
                {['Normal', 'Useful', 'Important', 'Very important'].map((v, i) => (
                  <option key={v} value={i}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={pinned}
                onChange={(e) => setPinned(e.target.checked)}
                disabled={saving}
              />
              Pin when relevant
            </label>
          </div>
          <p className="privacy-note">{MEMORY_NOTICE}</p>
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}
          <div className="memory-actions">
            <button type="button" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button className="primary-button" type="submit" disabled={saving || !content.trim()}>
              {saving ? 'Saving…' : initial ? 'Save revision' : 'Confirm & save memory'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
