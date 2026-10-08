//! Assign a suspended Core to its lifetime guard before any descendants can start.
use std::{
    io,
    process::{Child, Command},
};
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE},
    System::{
        Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, Thread32First, Thread32Next, TH32CS_SNAPTHREAD, THREADENTRY32,
        },
        JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
            SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
            JOB_OBJECT_LIMIT_BREAKAWAY_OK, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        },
        Threading::{
            OpenThread, ResumeThread, CREATE_NO_WINDOW, CREATE_SUSPENDED, THREAD_SUSPEND_RESUME,
        },
    },
};

pub(crate) struct WindowsJob(HANDLE);
unsafe impl Send for WindowsJob {}

impl WindowsJob {
    pub(crate) fn attach(child: &Child) -> Result<Self, String> {
        use std::os::windows::io::AsRawHandle;
        // Guard owns this handle; all pointers reference initialized memory.
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() {
                return Err(format!(
                    "Cannot create KAT Core lifetime guard: {}",
                    io::Error::last_os_error()
                ));
            }
            let job = Self(handle);
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            // Ordinary descendants stay owned. Only approved application launches
            // explicitly request CREATE_BREAKAWAY_FROM_JOB from Python.
            info.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK;
            if SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                std::mem::size_of_val(&info) as u32,
            ) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle()) == 0
            {
                return Err(format!(
                    "Cannot guard KAT Core lifetime: {}",
                    io::Error::last_os_error()
                ));
            }
            Ok(job)
        }
    }
}
impl Drop for WindowsJob {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}

pub(crate) fn spawn(mut command: Command) -> io::Result<(Child, WindowsJob)> {
    use std::os::windows::process::CommandExt;
    command.creation_flags(CREATE_NO_WINDOW | CREATE_SUSPENDED);
    let mut child = command.spawn()?;
    let result = WindowsJob::attach(&child)
        .map_err(io::Error::other)
        .and_then(|job| {
            resume_main_thread(child.id())?;
            Ok(job)
        });
    match result {
        Ok(job) => Ok((child, job)),
        Err(error) => {
            let _ = child.kill();
            let _ = child.wait();
            Err(error)
        }
    }
}

fn resume_main_thread(pid: u32) -> io::Result<()> {
    // Rust Child exposes the process handle but not CreateProcess's thread handle.
    // A newly created suspended process has one thread and cannot spawn another
    // before it resumes. Enumerate only that live child's PID, holding Child ownership.
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if snapshot == INVALID_HANDLE_VALUE {
            return Err(io::Error::last_os_error());
        }
        let mut entry: THREADENTRY32 = std::mem::zeroed();
        entry.dwSize = std::mem::size_of_val(&entry) as u32;
        let mut found = Thread32First(snapshot, &mut entry);
        let mut result = Err(io::Error::other(
            "Suspended KAT Core main thread was not found",
        ));
        while found != 0 {
            if entry.th32OwnerProcessID == pid {
                let thread = OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID);
                result = if thread.is_null() {
                    Err(io::Error::last_os_error())
                } else {
                    let resumed = ResumeThread(thread);
                    let outcome = if resumed == u32::MAX {
                        Err(io::Error::last_os_error())
                    } else {
                        Ok(())
                    };
                    CloseHandle(thread);
                    outcome
                };
                break;
            }
            found = Thread32Next(snapshot, &mut entry);
        }
        CloseHandle(snapshot);
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        fs, thread,
        time::{Duration, Instant},
    };
    use windows_sys::Win32::{
        Foundation::WAIT_TIMEOUT,
        System::Threading::{
            OpenProcess, TerminateProcess, WaitForSingleObject, CREATE_BREAKAWAY_FROM_JOB,
            PROCESS_SYNCHRONIZE, PROCESS_TERMINATE,
        },
    };

    #[test]
    #[ignore = "subprocess fixture invoked only by Windows lifetime tests"]
    fn launcher_fixture() {
        use std::os::windows::process::CommandExt;
        let mut command = Command::new(std::env::current_exe().unwrap());
        command.args(["--exact", "tests::sleeper_fixture", "--ignored"]);
        if std::env::var_os("KAT_NATIVE_FIXTURE_BREAKAWAY").is_some() {
            command.creation_flags(CREATE_BREAKAWAY_FROM_JOB);
        }
        let mut child = command.spawn().unwrap();
        let path =
            std::path::PathBuf::from(std::env::var_os("KAT_NATIVE_DESCENDANT_PID_FILE").unwrap());
        let temporary = path.with_extension("tmp");
        fs::write(&temporary, child.id().to_string()).unwrap();
        fs::rename(temporary, path).unwrap();
        thread::sleep(Duration::from_secs(30));
        child.wait().unwrap();
    }

    fn verify_tree(breakaway: bool) {
        let path =
            std::env::temp_dir().join(format!("kat-job-{}-{breakaway}.pid", std::process::id()));
        let _ = fs::remove_file(&path);
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "--exact",
                "windows_job::tests::launcher_fixture",
                "--ignored",
            ])
            .env("KAT_NATIVE_DESCENDANT_PID_FILE", &path);
        if breakaway {
            command.env("KAT_NATIVE_FIXTURE_BREAKAWAY", "1");
        }
        let (mut child, job) = spawn(command).unwrap();
        let deadline = Instant::now() + Duration::from_secs(5);
        while !path.exists() && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(20));
        }
        let pid: u32 = fs::read_to_string(&path)
            .expect("launcher must create its descendant")
            .parse()
            .unwrap();
        unsafe {
            let descendant = OpenProcess(PROCESS_SYNCHRONIZE | PROCESS_TERMINATE, 0, pid);
            assert!(
                !descendant.is_null(),
                "owned fixture descendant must be alive"
            );
            child.kill().unwrap();
            child.wait().unwrap();
            drop(job);
            let result = WaitForSingleObject(descendant, if breakaway { 200 } else { 5000 });
            // Always clean up the fixture, even when the assertion below fails.
            TerminateProcess(descendant, 1);
            WaitForSingleObject(descendant, 5000);
            CloseHandle(descendant);
            fs::remove_file(path).unwrap();
            if breakaway {
                assert_eq!(
                    result, WAIT_TIMEOUT,
                    "explicitly approved application must survive"
                );
            } else {
                assert_eq!(
                    result, 0,
                    "ordinary Core descendant must terminate with its job"
                );
            }
        }
    }
    #[test]
    fn ordinary_core_descendants_cannot_escape() {
        verify_tree(false);
    }
    #[test]
    fn explicit_application_breakaway_survives() {
        verify_tree(true);
    }
}
