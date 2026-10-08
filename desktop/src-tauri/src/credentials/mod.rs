//! Provider secrets stay in native code and never cross the webview boundary.

#[cfg(windows)]
mod windows;

use crate::CoreConnection;
use serde::Serialize;
use std::{env, process::Command};
use zeroize::Zeroizing;

// The generic Windows credential dialog supports passwords up to 256 characters.
// This includes current OpenAI project/service-account keys (not just legacy keys).
#[cfg(any(windows, test))]
const MAX_KEY_BYTES: usize = 256;

/// Deliberately has neither Debug nor Serialize; its owned allocation clears on drop.
struct ProviderSecret(Zeroizing<String>);

#[cfg(any(windows, test))]
impl ProviderSecret {
    fn validate(value: String) -> Result<Self, CredentialError> {
        let secret = Self(Zeroizing::new(value));
        if secret.0.len() < 16
            || secret.0.len() > MAX_KEY_BYTES
            || !secret.0.starts_with("sk-")
            || !secret
                .0
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
        {
            return Err(CredentialError::InvalidKey);
        }
        Ok(secret)
    }
}

#[derive(Clone, Copy, Debug, Serialize)]
pub struct ProviderCredentialsStatus {
    pub supported: bool,
    pub stored: bool,
    pub environment_configured: bool,
}

#[derive(Serialize)]
pub struct CredentialChangeResult {
    pub changed: bool,
    pub connection: Option<CoreConnection>,
    pub status: ProviderCredentialsStatus,
}

// Never wrap OS errors or values entered into the dialog: errors are fixed text.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(not(windows), allow(dead_code))]
enum CredentialError {
    Unsupported,
    Read,
    Write,
    Delete,
    Prompt,
    InvalidKey,
    InvalidEnvironment,
}

impl CredentialError {
    fn message(self) -> &'static str {
        match self {
            Self::Unsupported => "Secure API-key storage is available in the Windows desktop app. Use a process environment or ignored .env file on this platform.",
            Self::Read => "Windows Credential Manager could not read KAT's API key. Check your Windows account access or remove and save the key again.",
            Self::Write => "Windows Credential Manager could not save the API key. The existing key and running Core were left unchanged.",
            Self::Delete => "Windows Credential Manager could not remove the API key. KAT Core was not restarted.",
            Self::Prompt => "Windows could not open the API-key dialog. Try again from the desktop Settings screen.",
            Self::InvalidKey => "Enter an OpenAI API key beginning with sk-, containing 16–256 letters, digits, hyphens or underscores. The key was not saved.",
            Self::InvalidEnvironment => "The configured provider API-key environment variable is not valid Unicode. Correct it outside KAT and restart the desktop.",
        }
    }
}

trait CredentialStore {
    fn supported(&self) -> bool;
    fn contains(&self) -> Result<bool, CredentialError>;
    fn read(&self) -> Result<Option<ProviderSecret>, CredentialError>;
    fn write(&self, secret: &ProviderSecret) -> Result<(), CredentialError>;
    /// An already absent credential is a successful, unchanged removal.
    fn remove(&self) -> Result<bool, CredentialError>;
}

#[cfg(windows)]
use windows::WindowsCredentialStore as NativeCredentialStore;

#[cfg(not(windows))]
struct NativeCredentialStore;

#[cfg(not(windows))]
impl CredentialStore for NativeCredentialStore {
    fn supported(&self) -> bool {
        false
    }

    fn contains(&self) -> Result<bool, CredentialError> {
        Ok(false)
    }

    fn read(&self) -> Result<Option<ProviderSecret>, CredentialError> {
        Ok(None)
    }

    fn write(&self, _secret: &ProviderSecret) -> Result<(), CredentialError> {
        Err(CredentialError::Unsupported)
    }

    fn remove(&self) -> Result<bool, CredentialError> {
        Err(CredentialError::Unsupported)
    }
}

fn environment_configured() -> bool {
    ["KAT_OPENAI_API_KEY", "OPENAI_API_KEY"]
        .iter()
        .any(|name| env::var_os(name).is_some_and(|value| !value.is_empty()))
}

fn status<S: CredentialStore>(
    store: &S,
    environment_configured: bool,
) -> Result<ProviderCredentialsStatus, CredentialError> {
    Ok(ProviderCredentialsStatus {
        supported: store.supported(),
        stored: store.contains()?,
        environment_configured,
    })
}

pub fn provider_credentials_status() -> Result<ProviderCredentialsStatus, String> {
    status(&NativeCredentialStore, environment_configured()).map_err(|error| error.message().into())
}

fn configure<S, P, R>(
    store: &S,
    environment_configured: bool,
    prompt: P,
    restart: R,
) -> Result<CredentialChangeResult, String>
where
    S: CredentialStore,
    P: FnOnce() -> Result<Option<ProviderSecret>, CredentialError>,
    R: FnOnce() -> Result<CoreConnection, String>,
{
    if !store.supported() {
        return Err(CredentialError::Unsupported.message().into());
    }
    let Some(secret) = prompt().map_err(|error| error.message().to_owned())? else {
        return Ok(CredentialChangeResult {
            changed: false,
            connection: None,
            status: status(store, environment_configured)
                .map_err(|error| error.message().to_owned())?,
        });
    };
    store
        .write(&secret)
        .map_err(|error| error.message().to_owned())?;
    drop(secret);
    finish_change(store, environment_configured, true, restart, "saved")
}

fn remove<S, R>(
    store: &S,
    environment_configured: bool,
    restart: R,
) -> Result<CredentialChangeResult, String>
where
    S: CredentialStore,
    R: FnOnce() -> Result<CoreConnection, String>,
{
    if !store.supported() {
        return Err(CredentialError::Unsupported.message().into());
    }
    let changed = store.remove().map_err(|error| error.message().to_owned())?;
    finish_change(store, environment_configured, changed, restart, "removed")
}

fn finish_change<S, R>(
    store: &S,
    environment_configured: bool,
    changed: bool,
    restart: R,
    operation: &str,
) -> Result<CredentialChangeResult, String>
where
    S: CredentialStore,
    R: FnOnce() -> Result<CoreConnection, String>,
{
    let connection = if changed {
        Some(restart().map_err(|_| {
            format!("The API key was {operation}, but KAT Core could not restart. Use Restart Core and inspect the local startup log if it still fails.")
        })?)
    } else {
        None
    };
    Ok(CredentialChangeResult {
        changed,
        connection,
        status: status(store, environment_configured)
            .map_err(|error| error.message().to_owned())?,
    })
}

/// This is invoked on a blocking native worker, never with key data from JavaScript.
/// The HWND is captured from the invoking KAT window; zero means no parent.
pub fn configure_provider_credentials<R>(
    parent_window: usize,
    restart: R,
) -> Result<CredentialChangeResult, String>
where
    R: FnOnce() -> Result<CoreConnection, String>,
{
    #[cfg(windows)]
    let prompt = || windows::prompt(parent_window);
    #[cfg(not(windows))]
    let prompt = || {
        let _ = parent_window;
        Err(CredentialError::Unsupported)
    };
    configure(
        &NativeCredentialStore,
        environment_configured(),
        prompt,
        restart,
    )
}

pub fn remove_provider_credentials<R>(restart: R) -> Result<CredentialChangeResult, String>
where
    R: FnOnce() -> Result<CoreConnection, String>,
{
    remove(&NativeCredentialStore, environment_configured(), restart)
}

fn resolve_secret<S, E>(
    store: &S,
    mut environment: E,
) -> Result<Option<ProviderSecret>, CredentialError>
where
    S: CredentialStore,
    E: FnMut(&str) -> Result<Option<String>, CredentialError>,
{
    for name in ["KAT_OPENAI_API_KEY", "OPENAI_API_KEY"] {
        if let Some(value) = environment(name)? {
            let value = Zeroizing::new(value);
            if !value.is_empty() {
                // Environment keys are owned by configuration, not the native dialog.
                return Ok(Some(ProviderSecret(value)));
            }
        }
    }
    store.read()
}

/// Resolve only for the fixed owned Core child; never mutate process-global env.
/// Process configuration wins over Credential Manager, which wins over dev dotenv.
pub(crate) fn configure_core_environment(command: &mut Command) -> Result<(), String> {
    let secret = resolve_secret(&NativeCredentialStore, |name| match env::var(name) {
        Ok(value) => Ok(Some(value)),
        Err(env::VarError::NotPresent) => Ok(None),
        Err(env::VarError::NotUnicode(_)) => Err(CredentialError::InvalidEnvironment),
    })
    .map_err(|error| error.message().to_owned())?;
    if let Some(secret) = secret {
        // Normalize OPENAI_API_KEY into KAT's preferred alias so an optional .env
        // cannot override a process-level key by setting the other alias.
        command.env("KAT_OPENAI_API_KEY", secret.0.as_str());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::{Cell, RefCell};

    struct FakeStore {
        stored: RefCell<Option<String>>,
        reads: Cell<usize>,
        failure: Option<CredentialError>,
    }

    impl FakeStore {
        fn new(value: Option<&str>) -> Self {
            Self {
                stored: RefCell::new(value.map(str::to_owned)),
                reads: Cell::new(0),
                failure: None,
            }
        }
    }

    impl CredentialStore for FakeStore {
        fn supported(&self) -> bool {
            true
        }
        fn contains(&self) -> Result<bool, CredentialError> {
            Ok(self.stored.borrow().is_some())
        }
        fn read(&self) -> Result<Option<ProviderSecret>, CredentialError> {
            self.reads.set(self.reads.get() + 1);
            self.stored
                .borrow()
                .clone()
                .map(ProviderSecret::validate)
                .transpose()
        }
        fn write(&self, secret: &ProviderSecret) -> Result<(), CredentialError> {
            if let Some(error) = self.failure {
                return Err(error);
            }
            self.stored.replace(Some(secret.0.to_string()));
            Ok(())
        }
        fn remove(&self) -> Result<bool, CredentialError> {
            if let Some(error) = self.failure {
                return Err(error);
            }
            Ok(self.stored.take().is_some())
        }
    }

    // Synthetic key used exclusively with fake storage; never authenticates anywhere.
    const FAKE_KEY: &str = "sk-proj-test_fixture_only_1234567890";

    fn connection() -> Result<CoreConnection, String> {
        Ok(CoreConnection {
            base_url: "http://127.0.0.1:42800".into(),
            token: "local-test-token".into(),
        })
    }

    #[test]
    fn native_input_accepts_modern_project_keys_and_rejects_untrusted_content() {
        assert!(ProviderSecret::validate(format!("sk-proj-{}", "x".repeat(200))).is_ok());
        for value in [
            "",
            "not-a-key",
            "sk-proj-contains\nnewline",
            "sk-proj-$(shell)injection",
            "sk-proj-secret with space",
        ] {
            let error = ProviderSecret::validate(value.to_owned()).err().unwrap();
            assert_eq!(error, CredentialError::InvalidKey);
            assert!(!error.message().contains(value) || value.is_empty());
        }
        assert!(ProviderSecret::validate(format!("sk-proj-{}", "x".repeat(249))).is_err());
    }

    #[test]
    fn process_alias_precedence_never_reads_stored_key() {
        let store = FakeStore::new(Some(FAKE_KEY));
        let mut visited = Vec::new();
        let secret = resolve_secret(&store, |name| {
            visited.push(name.to_owned());
            Ok(Some("process-key".into()))
        })
        .unwrap()
        .unwrap();
        assert_eq!(secret.0.as_str(), "process-key");
        assert_eq!(visited, ["KAT_OPENAI_API_KEY"]);
        assert_eq!(store.reads.get(), 0);
    }

    #[test]
    fn openai_process_alias_precedes_storage_and_empty_alias_is_ignored() {
        let store = FakeStore::new(Some(FAKE_KEY));
        let secret = resolve_secret(&store, |name| {
            Ok(Some(
                if name == "KAT_OPENAI_API_KEY" {
                    ""
                } else {
                    "openai-process"
                }
                .into(),
            ))
        })
        .unwrap()
        .unwrap();
        assert_eq!(secret.0.as_str(), "openai-process");
        assert_eq!(store.reads.get(), 0);
        let secret = resolve_secret(&store, |_| Ok(None)).unwrap().unwrap();
        assert_eq!(secret.0.as_str(), FAKE_KEY);
        assert_eq!(store.reads.get(), 1);
    }

    #[test]
    fn status_has_only_boolean_presence_fields() {
        let store = FakeStore::new(Some(FAKE_KEY));
        let serialized = serde_json::to_value(status(&store, true).unwrap()).unwrap();
        assert_eq!(
            serialized,
            serde_json::json!({"supported":true,"stored":true,"environment_configured":true})
        );
        assert!(!serialized.to_string().contains(FAKE_KEY));
        assert_eq!(store.reads.get(), 0);
    }

    #[test]
    fn cancel_never_writes_or_restarts() {
        let store = FakeStore::new(Some(FAKE_KEY));
        let result = configure(&store, false, || Ok(None), || panic!("must not restart")).unwrap();
        assert!(!result.changed);
        assert!(result.connection.is_none());
        assert!(result.status.stored);
        assert_eq!(store.stored.borrow().as_deref(), Some(FAKE_KEY));
    }

    #[test]
    fn failed_write_leaves_core_and_existing_key_unchanged() {
        let mut store = FakeStore::new(Some(FAKE_KEY));
        store.failure = Some(CredentialError::Write);
        let error = configure(
            &store,
            false,
            || ProviderSecret::validate(FAKE_KEY.into()).map(Some),
            || panic!("must not restart"),
        )
        .err()
        .unwrap();
        assert_eq!(error, CredentialError::Write.message());
        assert!(!error.contains(FAKE_KEY));
        assert_eq!(store.stored.borrow().as_deref(), Some(FAKE_KEY));
    }

    #[test]
    fn successful_save_restarts_after_persistence_and_returns_no_key() {
        let store = FakeStore::new(None);
        let result = configure(
            &store,
            true,
            || ProviderSecret::validate(FAKE_KEY.into()).map(Some),
            || {
                assert!(store.contains().unwrap());
                connection()
            },
        )
        .unwrap();
        assert!(result.changed);
        assert!(result.connection.is_some());
        assert!(result.status.stored && result.status.environment_configured);
        let serialized = serde_json::to_string(&result).unwrap();
        assert!(!serialized.contains(FAKE_KEY));
        assert!(!serialized.contains("api_key"));
    }

    #[test]
    fn restart_failure_reports_saved_state_without_echoing_worker_error() {
        let store = FakeStore::new(None);
        let error = configure(
            &store,
            false,
            || ProviderSecret::validate(FAKE_KEY.into()).map(Some),
            || Err(format!("failure {FAKE_KEY}")),
        )
        .err()
        .unwrap();
        assert!(error.contains("was saved"));
        assert!(!error.contains(FAKE_KEY));
        assert!(status(&store, false).unwrap().stored);
    }

    #[test]
    fn remove_restarts_only_after_actual_success_and_reports_failure_state() {
        let store = FakeStore::new(Some(FAKE_KEY));
        let error = remove(&store, false, || Err(format!("failure {FAKE_KEY}")))
            .err()
            .unwrap();
        assert!(error.contains("was removed"));
        assert!(!error.contains(FAKE_KEY));
        assert!(!status(&store, false).unwrap().stored);
        let result = remove(&store, false, || panic!("absent key needs no restart")).unwrap();
        assert!(!result.changed);
        assert!(result.connection.is_none());
    }

    #[test]
    fn remove_failure_does_not_restart() {
        let mut store = FakeStore::new(Some(FAKE_KEY));
        store.failure = Some(CredentialError::Delete);
        let error = remove(&store, false, || panic!("must not restart"))
            .err()
            .unwrap();
        assert_eq!(error, CredentialError::Delete.message());
        assert!(status(&store, false).unwrap().stored);
    }

    #[cfg(not(windows))]
    #[test]
    fn unsupported_platform_does_not_prompt_or_restart() {
        let result = configure(
            &NativeCredentialStore,
            false,
            || panic!("must not prompt"),
            || panic!("must not restart"),
        );
        assert_eq!(
            result.err().unwrap(),
            CredentialError::Unsupported.message()
        );
        assert!(!status(&NativeCredentialStore, false).unwrap().supported);
        assert!(resolve_secret(&NativeCredentialStore, |_| Ok(None))
            .unwrap()
            .is_none());
    }
}
