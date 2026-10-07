import { useEffect, useState } from 'react';
import { CheckCircle2, KeyRound, Save, ShieldCheck } from 'lucide-react';
import type { Settings, SettingsUpdate } from './types';

interface Props {
  settings: Settings | null;
  saving: boolean;
  saved: boolean;
  onSave: (settings: SettingsUpdate) => void;
}

export function SettingsView({ settings, saving, saved, onSave }: Props) {
  const [model, setModel] = useState('');
  const [requireApproval, setRequireApproval] = useState(false);
  useEffect(() => {
    if (settings) {
      setModel(settings.model);
      setRequireApproval(settings.require_approval_for_low_risk);
    }
  }, [settings]);
  return (
    <main className="content-view">
      <header className="workspace-header">
        <div>
          <span className="eyebrow">WORKSPACE / PREFERENCES</span>
          <h1>Settings</h1>
        </div>
        <ShieldCheck size={23} className="muted" />
      </header>
      <div className="settings-content">
        <p className="page-intro">Make KAT feel at home. Your configuration is saved locally.</p>
        {!settings ? (
          <p role="status" className="muted">
            Loading settings…
          </p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSave({
                provider: 'openai',
                model: model.trim(),
                require_approval_for_low_risk: requireApproval,
              });
            }}
          >
            <section className="settings-card">
              <div className="card-heading">
                <div>
                  <h2>Model connection</h2>
                  <p>Choose the model KAT uses for conversations.</p>
                </div>
                <span className="section-number">01</span>
              </div>
              <label htmlFor="provider">Provider</label>
              <select id="provider" value="openai" disabled>
                <option value="openai">OpenAI</option>
              </select>
              <p className="field-hint">
                Additional providers can be added through the Core adapter interface.
              </p>
              <label htmlFor="model">Model</label>
              <input
                id="model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="gpt-4.1-mini"
                required
                maxLength={120}
                pattern={'[A-Za-z0-9][A-Za-z0-9._:\\-]{0,119}'}
                disabled={saving}
              />
              <p className="field-hint">Use a model available to your OpenAI account.</p>
              <div className={`key-status ${settings.api_key_configured ? 'configured' : ''}`}>
                <KeyRound size={19} />
                <div>
                  <strong>{settings.api_key_configured ? 'API key configured' : 'API key required'}</strong>
                  <span>
                    Set OPENAI_API_KEY in your local Core environment, then restart KAT. Keys stay outside the
                    desktop interface.
                  </span>
                </div>
              </div>
              <p className="data-note">
                History is stored on this device. Conversation context is sent to OpenAI.
              </p>
            </section>
            <section className="settings-card">
              <div className="card-heading">
                <div>
                  <h2>Permissions</h2>
                  <p>You decide when KAT can act.</p>
                </div>
                <span className="section-number">02</span>
              </div>
              <label className="checkbox-row" htmlFor="approval-setting">
                <input
                  type="checkbox"
                  id="approval-setting"
                  checked={requireApproval}
                  onChange={(event) => setRequireApproval(event.target.checked)}
                  disabled={saving}
                />
                <span>
                  <strong>Ask before low-risk tools</strong>
                  <small>Require approval for tools such as reading the local time.</small>
                </span>
              </label>
              <p className="permission-note">
                <ShieldCheck size={16} /> Opening an application always requires your approval.
              </p>
              <h3>Allowed applications</h3>
              {settings.application_allowlist.length === 0 ? (
                <p className="muted">
                  No applications are configured. Add approved applications in the Core configuration.
                </p>
              ) : (
                <div className="application-list">
                  {settings.application_allowlist.map((app) => (
                    <div key={app.id}>
                      <span>{app.label}</span>
                      <code>{app.id}</code>
                    </div>
                  ))}
                </div>
              )}
              <p className="field-hint">
                KAT can only open these explicit applications. Shell commands and arbitrary executable paths
                are unavailable.
              </p>
            </section>
            <div className="settings-actions">
              <span role="status" className="saved-message">
                {saved && (
                  <>
                    <CheckCircle2 size={16} /> Settings saved
                  </>
                )}
              </span>
              <button type="submit" className="primary-button" disabled={saving || !model.trim()}>
                <Save size={16} />
                {saving ? 'Saving…' : 'Save settings'}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
