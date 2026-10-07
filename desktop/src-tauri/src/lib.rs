//! Owned local core process lifecycle, kept independent of the webview for tests.

use serde::Serialize;
#[cfg(target_os = "linux")]
mod linux_guardian;
use std::{
    fs::{self, OpenOptions},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant},
};

pub const CORE_PORT: u16 = 42800;
pub const CORE_BASE_URL: &str = "http://127.0.0.1:42800";

/// This value is sent only to the trusted local webview and never logged.
#[derive(Clone, Serialize)]
pub struct CoreConnection {
    pub base_url: String,
    pub token: String,
}

pub struct LaunchSpec {
    pub executable: PathBuf,
    pub arguments: Vec<String>,
    pub working_directory: PathBuf,
}

/// Locate only the configured core executable; never resolve programs through PATH.
pub fn development_spec(repo: &Path, windows: bool) -> Result<LaunchSpec, String> {
    let executable = repo.join(if windows {
        "core/.venv/Scripts/python.exe"
    } else {
        "core/.venv/bin/python"
    });
    if !executable.is_file() {
        return Err(format!(
            "KAT Core Python environment is missing at {}. Run the documented core setup first.",
            executable.display()
        ));
    }
    let mut arguments = vec!["-m".into(), "kat_core".into()];
    let env_file = repo.join(".env");
    if env_file.is_file() {
        arguments.extend(["--env-file".into(), env_file.to_string_lossy().into_owned()]);
    }
    Ok(LaunchSpec {
        executable,
        arguments,
        working_directory: repo.to_owned(),
    })
}

pub fn packaged_spec(resource_dir: &Path, windows: bool) -> Result<LaunchSpec, String> {
    let executable = resource_dir.join(if windows {
        "binaries/kat-core/kat-core.exe"
    } else {
        "binaries/kat-core/kat-core"
    });
    if !executable.is_file() {
        return Err(format!(
            "The packaged KAT Core is missing at {}. Rebuild with scripts/build-windows.ps1.",
            executable.display()
        ));
    }
    Ok(LaunchSpec {
        executable,
        arguments: Vec::new(),
        working_directory: resource_dir.to_owned(),
    })
}

pub fn new_token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::getrandom(&mut bytes)
        .map_err(|_| "The operating system could not generate a secure API token.".to_owned())?;
    Ok(bytes.iter().map(|value| format!("{value:02x}")).collect())
}

pub fn ensure_port_available(port: u16) -> Result<(), String> {
    TcpListener::bind(("127.0.0.1", port))
        .map(drop)
        .map_err(|error| {
            format!(
                "KAT Core cannot use 127.0.0.1:{port}: {error}. Close another KAT instance or the program using this port, then retry."
            )
        })
}

/// Owns the child process and bearer credential; dropping it always reaps the child.
pub struct CoreProcess {
    child: Child,
    connection: CoreConnection,
    #[cfg(windows)]
    _job: WindowsJob,
    #[cfg(target_os = "linux")]
    _guardian: Option<linux_guardian::Guardian>,
}

impl CoreProcess {
    pub fn start(spec: &LaunchSpec, data_dir: &Path) -> Result<Self, String> {
        ensure_port_available(CORE_PORT)?;
        let token = new_token()?;
        let log_dir = data_dir.join("logs");
        fs::create_dir_all(&log_dir)
            .map_err(|error| format!("Cannot create KAT log directory: {error}"))?;
        let log_path = log_dir.join("desktop-core.log");
        let stdout = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|error| format!("Cannot open KAT Core startup log: {error}"))?;
        let stderr = stdout
            .try_clone()
            .map_err(|error| format!("Cannot attach KAT Core error log: {error}"))?;
        let mut command = Command::new(&spec.executable);
        command
            .args(&spec.arguments)
            .current_dir(&spec.working_directory)
            .env("KAT_API_TOKEN", &token)
            .env("KAT_DATA_DIR", data_dir)
            .env("KAT_HOST", "127.0.0.1")
            .env("KAT_PORT", CORE_PORT.to_string())
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr));
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        #[cfg(target_os = "linux")]
        let spawned = linux_guardian::spawn(command);
        #[cfg(not(target_os = "linux"))]
        let spawned = command.spawn();
        let spawned = spawned.map_err(|error| {
            format!(
                "Could not launch KAT Core at {}: {error}",
                spec.executable.display()
            )
        })?;
        #[cfg(target_os = "linux")]
        let (child, guardian) = spawned;
        #[cfg(not(target_os = "linux"))]
        let child = spawned;
        #[cfg(windows)]
        let job = match WindowsJob::attach(&child) {
            Ok(job) => job,
            Err(error) => {
                let mut child = child;
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        };
        let mut process = Self {
            child,
            connection: CoreConnection {
                base_url: CORE_BASE_URL.into(),
                token,
            },
            #[cfg(windows)]
            _job: job,
            #[cfg(target_os = "linux")]
            _guardian: Some(guardian),
        };
        wait_until_ready(
            &mut process.child,
            &process.connection,
            Duration::from_secs(25),
        )
        .map_err(|error| format!("{error} See {} for details.", log_path.display()))?;
        Ok(process)
    }

    pub fn connection(&mut self) -> Result<CoreConnection, String> {
        match self.child.try_wait() {
            Ok(None) => Ok(self.connection.clone()),
            Ok(Some(status)) => Err(format!(
                "KAT Core exited ({status}). Restart Core or inspect the local logs."
            )),
            Err(error) => Err(format!("Cannot inspect KAT Core process: {error}")),
        }
    }
}

/// A Windows kernel handle closes automatically even after an abrupt desktop exit.
/// Only Core belongs to this job: applications launched by tools break away silently.
#[cfg(windows)]
struct WindowsJob(windows_sys::Win32::Foundation::HANDLE);

#[cfg(windows)]
unsafe impl Send for WindowsJob {}

#[cfg(windows)]
impl WindowsJob {
    fn attach(child: &Child) -> Result<Self, String> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::System::JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
            SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK,
        };
        // Handles are owned by this guard; all pointers reference initialized memory.
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() {
                return Err(format!(
                    "Cannot create KAT Core lifetime guard: {}",
                    std::io::Error::last_os_error()
                ));
            }
            let job = Self(handle);
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK;
            if SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const std::ffi::c_void,
                std::mem::size_of_val(&info) as u32,
            ) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle()) == 0
            {
                return Err(format!(
                    "Cannot guard KAT Core lifetime: {}",
                    std::io::Error::last_os_error()
                ));
            }
            Ok(job)
        }
    }
}

#[cfg(windows)]
impl Drop for WindowsJob {
    fn drop(&mut self) {
        unsafe {
            windows_sys::Win32::Foundation::CloseHandle(self.0);
        }
    }
}

impl Drop for CoreProcess {
    fn drop(&mut self) {
        // kill targets only this Child's PID, never other services on the fixed port.
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

pub fn wait_until_ready(
    child: &mut Child,
    connection: &CoreConnection,
    timeout: Duration,
) -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_millis(500))
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|error| format!("Cannot prepare local health check: {error}"))?;
    let started = Instant::now();
    while started.elapsed() < timeout {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| format!("Cannot inspect KAT Core process: {error}"))?
        {
            return Err(format!("KAT Core exited during startup ({status})."));
        }
        if let Ok(response) = client
            .get(format!("{}/health", connection.base_url))
            .bearer_auth(&connection.token)
            .send()
        {
            if response.status().is_success() {
                return Ok(());
            }
            if response.status() == reqwest::StatusCode::UNAUTHORIZED
                || response.status() == reqwest::StatusCode::FORBIDDEN
            {
                return Err("The local service rejected the owned KAT Core credential. Another process may have claimed its port.".into());
            }
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("KAT Core did not become ready within 25 seconds.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{Read, Write},
        sync::atomic::{AtomicUsize, Ordering},
    };

    static NEXT_DIR: AtomicUsize = AtomicUsize::new(0);

    fn temp_dir() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "kat-native-test-{}-{}",
            std::process::id(),
            NEXT_DIR.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn token_is_secure_length_hex_and_unique() {
        let first = new_token().unwrap();
        let second = new_token().unwrap();
        assert_eq!(first.len(), 64);
        assert!(first.bytes().all(|value| value.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[test]
    fn detects_port_conflicts_without_attaching() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let error = ensure_port_available(port).unwrap_err();
        assert!(error.contains("Close another KAT instance"));
        drop(listener);
        assert!(ensure_port_available(0).is_ok());
    }

    #[test]
    fn development_spec_uses_fixed_venv_and_optional_env_file() {
        let repo = temp_dir();
        assert!(development_spec(&repo, true).is_err());
        fs::create_dir_all(repo.join("core/.venv/Scripts")).unwrap();
        fs::write(repo.join("core/.venv/Scripts/python.exe"), b"test").unwrap();
        let spec = development_spec(&repo, true).unwrap();
        assert_eq!(spec.arguments, ["-m", "kat_core"]);
        fs::write(repo.join(".env"), b"unused").unwrap();
        let spec = development_spec(&repo, true).unwrap();
        assert_eq!(spec.arguments[2], "--env-file");
        assert_eq!(Path::new(&spec.arguments[3]), repo.join(".env"));
        fs::remove_dir_all(repo).unwrap();
    }

    #[test]
    fn packaged_spec_requires_bundled_executable() {
        let root = temp_dir();
        assert!(packaged_spec(&root, true).is_err());
        fs::create_dir_all(root.join("binaries/kat-core")).unwrap();
        fs::write(root.join("binaries/kat-core/kat-core.exe"), b"test").unwrap();
        let spec = packaged_spec(&root, true).unwrap();
        assert!(spec.arguments.is_empty());
        assert_eq!(spec.executable, root.join("binaries/kat-core/kat-core.exe"));
        fs::remove_dir_all(root).unwrap();
    }

    // An owned subprocess is a copy of this test binary, without shell invocation.
    fn sleeper_child() -> Child {
        Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "tests::sleeper_fixture", "--ignored"])
            .stdout(Stdio::null())
            .spawn()
            .unwrap()
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn linux_guardian_outlives_temporary_command_worker() {
        let (mut child, guardian) = thread::spawn(|| {
            let mut command = Command::new(std::env::current_exe().unwrap());
            command
                .args(["--exact", "tests::sleeper_fixture", "--ignored"])
                .stdout(Stdio::null());
            linux_guardian::spawn(command).unwrap()
        })
        .join()
        .unwrap();
        thread::sleep(Duration::from_millis(100));
        assert!(
            child.try_wait().unwrap().is_none(),
            "Core creator must outlive the transient restart worker"
        );
        child.kill().unwrap();
        child.wait().unwrap();
        drop(guardian);
    }

    #[test]
    #[ignore = "subprocess fixture invoked only by lifecycle tests"]
    fn sleeper_fixture() {
        thread::sleep(Duration::from_secs(30));
    }

    fn readiness_case(status: &str) -> Result<(), String> {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let address = listener.local_addr().unwrap();
        let response =
            format!("HTTP/1.1 {status}\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{{}}");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut request = [0_u8; 2048];
            let count = stream.read(&mut request).unwrap();
            let request = String::from_utf8_lossy(&request[..count]).to_lowercase();
            assert!(request.contains("authorization: bearer test-token\r\n"));
            stream.write_all(response.as_bytes()).unwrap();
        });
        let mut child = sleeper_child();
        let result = wait_until_ready(
            &mut child,
            &CoreConnection {
                base_url: format!("http://{address}"),
                token: "test-token".into(),
            },
            Duration::from_secs(3),
        );
        child.kill().unwrap();
        child.wait().unwrap();
        server.join().unwrap();
        result
    }

    #[test]
    fn readiness_sends_credential_and_accepts_success() {
        assert!(readiness_case("200 OK").is_ok());
    }

    #[test]
    fn readiness_rejects_wrong_service_credential() {
        let error = readiness_case("401 Unauthorized").unwrap_err();
        assert!(error.contains("rejected"));
    }

    #[test]
    fn dropping_owned_process_terminates_it() {
        let child = sleeper_child();
        #[cfg(windows)]
        let job = WindowsJob::attach(&child).unwrap();
        let mut process = CoreProcess {
            child,
            connection: CoreConnection {
                base_url: CORE_BASE_URL.into(),
                token: "unused".into(),
            },
            #[cfg(windows)]
            _job: job,
            #[cfg(target_os = "linux")]
            _guardian: None,
        };
        assert!(process.connection().is_ok());
        // Drop's kill+wait is exercised; a completed wait cannot leave a zombie.
        drop(process);
    }

    #[test]
    #[ignore = "integration smoke requires an installed Core and free port42800"]
    fn starts_real_core_and_releases_port() {
        let repo =
            PathBuf::from(std::env::var("KAT_NATIVE_TEST_REPO").expect("Set KAT_NATIVE_TEST_REPO"));
        let spec = development_spec(&repo, cfg!(windows)).unwrap();
        verify_core_launch(&spec);
    }

    #[test]
    #[ignore = "integration smoke requires a packaged Core and free port42800"]
    fn starts_packaged_core_and_releases_port() {
        let spec = packaged_spec(Path::new(env!("CARGO_MANIFEST_DIR")), cfg!(windows)).unwrap();
        verify_core_launch(&spec);
    }

    #[test]
    #[ignore = "integration regression requires a packaged Core and free port42800"]
    fn core_outlives_short_lived_start_thread() {
        let data_dir = temp_dir();
        let worker_data = data_dir.clone();
        let mut process = thread::spawn(move || {
            let spec = packaged_spec(Path::new(env!("CARGO_MANIFEST_DIR")), cfg!(windows)).unwrap();
            CoreProcess::start(&spec, &worker_data).unwrap()
        })
        .join()
        .unwrap();
        // Linux PDEATHSIG is associated with the creator thread. A live Core
        // must survive the exit of Tauri's temporary restart command worker.
        thread::sleep(Duration::from_millis(300));
        let connection = process.connection().unwrap();
        let response = reqwest::blocking::Client::new()
            .get(format!("{}/health", connection.base_url))
            .bearer_auth(&connection.token)
            .send()
            .unwrap();
        assert!(response.status().is_success());
        drop(process);
        assert!(ensure_port_available(CORE_PORT).is_ok());
        fs::remove_dir_all(data_dir).unwrap();
    }

    fn verify_core_launch(spec: &LaunchSpec) {
        let data_dir = temp_dir();
        let mut process = CoreProcess::start(spec, &data_dir).unwrap();
        let connection = process.connection().unwrap();
        let response = reqwest::blocking::Client::new()
            .get(format!("{}/health", connection.base_url))
            .send()
            .unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::UNAUTHORIZED);
        assert!(
            !data_dir.join("api-token").exists(),
            "native credential must remain ephemeral"
        );
        drop(process);
        assert!(
            ensure_port_available(CORE_PORT).is_ok(),
            "owned Core must release its listening port"
        );
        fs::remove_dir_all(data_dir).unwrap();
    }
}
