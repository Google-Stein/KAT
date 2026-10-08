import { KeyRound, Trash2 } from 'lucide-react';
import type { ProviderCredentialsStatus } from './types';

interface Props {
  configured: boolean;
  native: boolean;
  status: ProviderCredentialsStatus | null;
  loading: boolean;
  busy: boolean;
  notice: string | null;
  statusError: boolean;
  onRefresh: () => void;
  onConfigure: () => void;
  onRemove: () => void;
}

export function ProviderCredentialsView({
  configured,
  native,
  status,
  loading,
  busy,
  notice,
  statusError,
  onRefresh,
  onConfigure,
  onRemove,
}: Props) {
  const supported = native && status?.supported;
  return (
    <div className="provider-credentials">
      <div className={`key-status ${configured ? 'configured' : ''}`}>
        <KeyRound size={19} />
        <div>
          <strong>{configured ? 'API key configured' : 'API key required'}</strong>
          <span>
            {supported
              ? 'Enter your key in the Windows security dialog. KAT saves it in Windows Credential Manager.'
              : 'Set OPENAI_API_KEY or KAT_OPENAI_API_KEY in your local Core environment, then restart KAT. Keys stay outside the desktop interface.'}
          </span>
        </div>
      </div>
      {native && loading && (
        <p role="status" className="field-hint">
          Checking saved credentials…
        </p>
      )}
      {native && statusError && (
        <div className="credential-actions">
          <p className="field-hint">Could not check Windows credentials. Try again.</p>
          <button type="button" className="secondary-button" onClick={onRefresh} disabled={busy || loading}>
            Retry credential check
          </button>
        </div>
      )}
      {supported && (
        <>
          <p className="field-hint">
            {status.stored ? 'Windows saved key: present.' : 'Windows saved key: not set.'}{' '}
            {status.environment_configured
              ? 'A process environment key is configured and takes precedence over the saved key.'
              : 'No process environment key is configured.'}
          </p>
          <p className="field-hint">
            Paste the OpenAI API key into the dialog’s Password field. Do not enter your Windows account
            password.
          </p>
          <p className="field-hint">
            Core uses the process environment, then a Windows saved key, then the development .env file.
            Removing a saved key leaves environment and .env configuration available.
          </p>
          <div className="credential-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={onConfigure}
              disabled={busy || loading}
            >
              <KeyRound size={15} /> {status.stored ? 'Replace saved key' : 'Set API key'}
            </button>
            {status.stored && (
              <button
                type="button"
                className="secondary-button"
                onClick={onRemove}
                disabled={busy || loading}
              >
                <Trash2 size={15} /> Remove saved key
              </button>
            )}
          </div>
          <p className="field-hint">
            Saving or removing a key restarts local Core. Your conversations stay on this device. Keys never
            pass through this interface.
          </p>
        </>
      )}
      {native && status && !status.supported && (
        <p className="field-hint">Saved key management is available in the Windows desktop application.</p>
      )}
      {notice && (
        <p role="status" className="field-hint">
          {notice}
        </p>
      )}
    </div>
  );
}
