#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use kat_desktop::{development_spec, packaged_spec, CoreConnection, CoreProcess};
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

fn main() {
    let application = tauri::Builder::default()
        .setup(|app| {
            let data_dir = app.path().app_local_data_dir()?;
            let source = if !cfg!(feature = "custom-protocol") {
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
                data_dir,
            };
            let _ = runtime.restart();
            app.manage(Arc::new(Mutex::new(runtime)));
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
                        || (!cfg!(feature = "custom-protocol")
                            && url.scheme() == "http"
                            && url.host_str() == Some("127.0.0.1")
                            && url.port() == Some(1420))
                })
                .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
                .build()?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![core_connection, restart_core])
        .build(tauri::generate_context!())
        .expect("KAT could not initialize its desktop window");

    application.run(|app, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            if let Some(state) = app.try_state::<ManagedRuntime>() {
                if let Ok(mut runtime) = state.lock() {
                    runtime.process.take();
                }
            }
        }
    });
}
