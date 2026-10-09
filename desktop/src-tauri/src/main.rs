#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use kat_desktop::credentials::{self, CredentialChangeResult, ProviderCredentialsStatus};
use kat_desktop::{development_spec, log_event, packaged_spec, CoreConnection, CoreProcess};
use std::{
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

enum LaunchSource {
    Development(PathBuf),
    Packaged(PathBuf),
}

struct Runtime {
    process: Option<CoreProcess>,
    startup_error: Option<String>,
    source: LaunchSource,
    data_dir: PathBuf,
}

impl Runtime {
    fn restart(&mut self) -> Result<CoreConnection, String> {
        self.process.take();
        self.startup_error = None;
        let result = match &self.source {
            LaunchSource::Development(repo) => development_spec(repo, cfg!(windows)),
            LaunchSource::Packaged(resources) => packaged_spec(resources, cfg!(windows)),
        }
        .and_then(|spec| CoreProcess::start(&spec, &self.data_dir));
        match result {
            Ok(mut process) => {
                let connection = process.connection()?;
                self.process = Some(process);
                Ok(connection)
            }
            Err(error) => {
                log_event(&self.data_dir, "core_failed", &error);
                self.startup_error = Some(error.clone());
                Err(error)
            }
        }
    }
}

type ManagedRuntime = Arc<Mutex<Runtime>>;

#[tauri::command]
fn core_connection(state: tauri::State<'_, ManagedRuntime>) -> Result<CoreConnection, String> {
    let mut runtime = state
        .lock()
        .map_err(|_| "KAT runtime state is unavailable.")?;
    match runtime.process.as_mut() {
        Some(process) => process.connection(),
        None => Err(runtime
            .startup_error
            .clone()
            .unwrap_or_else(|| "KAT Core is not running.".into())),
    }
}

#[tauri::command]
async fn restart_core(state: tauri::State<'_, ManagedRuntime>) -> Result<CoreConnection, String> {
    let runtime = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || {
        runtime
            .lock()
            .map_err(|_| "KAT runtime state is unavailable.")?
            .restart()
    })
    .await
    .map_err(|_| "KAT Core restart worker failed.".to_owned())?
}

#[tauri::command]
async fn provider_credentials_status() -> Result<ProviderCredentialsStatus, String> {
    tauri::async_runtime::spawn_blocking(credentials::provider_credentials_status)
        .await
        .map_err(|_| "KAT credential status worker failed.".to_owned())?
}

#[tauri::command]
async fn configure_provider_credentials(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, ManagedRuntime>,
) -> Result<CredentialChangeResult, String> {
    #[cfg(windows)]
    let parent_window = window
        .hwnd()
        .map_err(|_| "KAT could not locate the desktop window.".to_owned())?
        .0 as usize;
    #[cfg(not(windows))]
    let parent_window = {
        let _ = window;
        0
    };
    let runtime = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || {
        let mut runtime = runtime
            .lock()
            .map_err(|_| "KAT runtime state is unavailable.")?;
        credentials::configure_provider_credentials(parent_window, || runtime.restart())
    })
    .await
    .map_err(|_| "KAT credential configuration worker failed.".to_owned())?
}

#[tauri::command]
async fn remove_provider_credentials(
    state: tauri::State<'_, ManagedRuntime>,
) -> Result<CredentialChangeResult, String> {
    let runtime = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || {
        let mut runtime = runtime
            .lock()
            .map_err(|_| "KAT runtime state is unavailable.")?;
        credentials::remove_provider_credentials(|| runtime.restart())
    })
    .await
    .map_err(|_| "KAT credential removal worker failed.".to_owned())?
}

#[tauri::command]
async fn choose_read_folder(window: tauri::WebviewWindow) -> Result<Option<String>, String> {
    #[cfg(windows)]
    let parent = window
        .hwnd()
        .map_err(|_| "KAT could not locate its window.")?
        .0 as usize;
    #[cfg(not(windows))]
    let parent = {
        let _ = window;
        0
    };
    tauri::async_runtime::spawn_blocking(move || kat_desktop::folder_picker::pick_folder(parent))
        .await
        .map_err(|_| "Folder selection worker failed.".to_owned())?
}

fn main() {
    let application = tauri::Builder::default()
        .setup(|app| {
            let data_dir = app.path().app_local_data_dir()?;
            log_event(
                &data_dir,
                "desktop_start",
                "initializing owned Core and window",
            );
            // Tauri CLI enables the dependency feature tauri/custom-protocol,
            // not necessarily our forwarding feature. Query the framework itself.
            let source = if tauri::is_dev() {
                let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .parent()
                    .and_then(|path| path.parent())
                    .ok_or("Cannot locate the KAT development checkout.")?
                    .to_owned();
                LaunchSource::Development(repo)
            } else {
                LaunchSource::Packaged(app.path().resource_dir()?)
            };
            // Preserve a usable window with a clear UI error when core startup fails.
            let mut runtime = Runtime {
                process: None,
                startup_error: None,
                source,
                data_dir: data_dir.clone(),
            };
            let _ = runtime.restart();
            app.manage(Arc::new(Mutex::new(runtime)));
            log_event(&data_dir, "window_creating", "WebView2 initialization");
            WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("KAT")
                .inner_size(1100.0, 780.0)
                .min_inner_size(720.0, 540.0)
                .center()
                .on_navigation(|url| {
                    (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
                        || (url.scheme() == "http"
                            && url.host_str() == Some("tauri.localhost")
                            && url.port().is_none())
                        || (tauri::is_dev()
                            && url.scheme() == "http"
                            && url.host_str() == Some("127.0.0.1")
                            && url.port() == Some(1420))
                })
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .build()
                .inspect_err(|error| {
                    log_event(&data_dir, "window_failed", &error.to_string());
                })?;
            log_event(&data_dir, "window_ready", "native window created");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_connection,
            restart_core,
            provider_credentials_status,
            configure_provider_credentials,
            remove_provider_credentials,
            choose_read_folder
        ])
        .build(tauri::generate_context!())
        .expect("KAT could not initialize its desktop window");

    application.run(|app, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            if let Some(state) = app.try_state::<ManagedRuntime>() {
                if let Ok(mut runtime) = state.lock() {
                    log_event(&runtime.data_dir, "desktop_exit", "stopping owned Core");
                    runtime.process.take();
                }
            }
        }
    });
}
