import { useEffect, useState } from 'react';
import { CheckCircle2, Save, ShieldCheck } from 'lucide-react';
import { ProviderCredentialsView } from './ProviderCredentialsView';
import type { ProviderCredentialsStatus, ProviderStatus, Settings, SettingsUpdate } from './types';

interface Props {
  settings: Settings | null;
  saving: boolean;
  saved: boolean;
  onSave: (settings: SettingsUpdate) => void;
  onProbe: (settings: SettingsUpdate) => Promise<ProviderStatus>;
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
  onProbe,
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
  const [provider, setProvider] = useState<Settings['provider']>('openai');
  const [endpoint, setEndpoint] = useState('http://127.0.0.1:11434');
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [probeError, setProbeError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (settings) {
      setProvider(settings.provider);
      setEndpoint(settings.local_endpoint);
    }
  }, [settings]);
  useEffect(() => {
    if (!model.trim() || !endpoint.trim()) return;
    let current = true;
    setStatus(null);
    setProbeError(false);
    setChecking(true);
    const timeout = setTimeout(() => {
      void onProbe({
        provider,
        model: model.trim(),
        local_endpoint: endpoint,
        require_approval_for_low_risk: false,
        memory_enabled: settings?.memory_enabled ?? false,
      })
        .then((result) => {
          if (current) setStatus(result);
        })
        .catch(() => {
          if (current) setProbeError(true);
        })
        .finally(() => {
          if (current) setChecking(false);
        });
    }, 400);
    return () => {
      current = false;
      clearTimeout(timeout);
    };
  }, [provider, model, endpoint, refresh, onProbe, settings?.memory_enabled]);
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
                provider,
                local_endpoint: endpoint,
                model: model.trim(),
                require_approval_for_low_risk: requireApproval,
                memory_enabled: settings.memory_enabled,
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
              <select
                id="provider"
                value={provider}
                disabled={saving}
                onChange={(event) => {
                  const next = event.target.value as Settings['provider'];
                  setProvider(next);
                  setModel(
                    next === settings.provider
                      ? settings.model
                      : next === 'ollama'
                        ? 'qwen3:8b'
                        : 'gpt-4.1-mini',
                  );
                }}
              >
                <option value="openai">OpenAI · cloud</option>
                <option value="ollama">Local · Ollama</option>
              </select>
              <p className="field-hint">
                Provider selection is explicit. Local failures never fall back to cloud.
              </p>
              {provider === 'ollama' && (
                <>
                  <label htmlFor="local-endpoint">Local backend address</label>
                  <input
                    id="local-endpoint"
                    value={endpoint}
                    onChange={(event) => setEndpoint(event.target.value)}
                    required
                    disabled={saving}
                  />
                  <p className="field-hint">
                    Install and run Ollama on this computer. Only loopback addresses are accepted.
                  </p>
                </>
              )}
              <label htmlFor="model">Model</label>
              <input
                id="model"
                list="available-models"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="gpt-4.1-mini"
                required
                maxLength={120}
                pattern={'[A-Za-z0-9][A-Za-z0-9._:\\-]{0,119}'}
                disabled={saving}
              />
              <datalist id="available-models">
                {status?.models.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
              <p className="field-hint">
                {provider === 'ollama'
                  ? 'Choose an installed model. Recommended for 24 GB VRAM: qwen3:8b (about 5 GB download, installed separately through Ollama).'
                  : 'Use a model available to your OpenAI account.'}
              </p>
              <div className="provider-status" role="status">
                {checking
                  ? 'Checking provider…'
                  : probeError
                    ? 'Could not check provider. Verify the address and Core connection.'
                    : status?.message}
                {provider === 'ollama' && status?.status === 'ready' && !status.tool_calling && (
                  <p>
                    This model cannot use KAT tools. Choose a tool-capable model for time and application
                    requests.
                  </p>
                )}
              </div>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setRefresh((value) => value + 1)}
                disabled={saving || checking}
              >
                Refresh provider status
              </button>
              {provider === 'openai' && (
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
              )}
              <p className="data-note">
                {provider === 'ollama'
                  ? 'History and inference stay on this computer. KAT does not download models or send these conversations to OpenAI.'
                  : 'History is stored on this device. Conversation context and tool descriptions are sent to OpenAI when you chat.'}
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
