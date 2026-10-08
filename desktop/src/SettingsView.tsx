import { useEffect, useState } from 'react';
import { CheckCircle2, Save, ShieldCheck } from 'lucide-react';
import { ProviderCredentialsView } from './ProviderCredentialsView';
import type { ProviderCredentialsStatus, Settings, SettingsUpdate } from './types';

interface Props {
  settings: Settings | null;
  saving: boolean;
  saved: boolean;
  onSave: (settings: SettingsUpdate) => void;
  native: boolean;
  credentials: ProviderCredentialsStatus | null;
  credentialsLoading: boolean;
  credentialsNotice: string | null;
  credentialsStatusError: boolean;
  credentialsChanging: boolean;
  onRefreshCredentials: () => void;
  onConfigureCredentials: () => void;
  onRemoveCredentials: () => void;
}

export function SettingsView({
  settings,
  saving,
  saved,
  onSave,
  native,
  credentials,
  credentialsLoading,
  credentialsNotice,
  credentialsStatusError,
  credentialsChanging,
  onRefreshCredentials,
  onConfigureCredentials,
  onRemoveCredentials,
}: Props) {
  const [model, setModel] = useState('');
  const [requireApproval, setRequireApproval] = useState(false);
  const savedModel = settings?.model;
  const savedRequireApproval = settings?.require_approval_for_low_risk;
  useEffect(() => {
    if (savedModel !== undefined) setModel(savedModel);
  }, [savedModel]);
  useEffect(() => {
    if (savedRequireApproval !== undefined) setRequireApproval(savedRequireApproval);
  }, [savedRequireApproval]);
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
              <ProviderCredentialsView
                configured={settings.api_key_configured}
                native={native}
                status={credentials}
                loading={credentialsLoading}
                busy={saving}
                notice={credentialsNotice}
                statusError={credentialsStatusError}
                onRefresh={onRefreshCredentials}
                onConfigure={onConfigureCredentials}
                onRemove={onRemoveCredentials}
              />
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
                {credentialsChanging ? 'Please wait…' : saving ? 'Saving…' : 'Save settings'}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
