//! Keep Linux's PDEATHSIG creator thread alive for the owned Core's lifetime.

use std::{
    io,
    os::unix::process::CommandExt,
    process::{Child, Command},
    sync::mpsc,
    thread::{self, JoinHandle},
};

pub(crate) struct Guardian {
    stop: mpsc::Sender<()>,
    worker: Option<JoinHandle<()>>,
}

pub(crate) fn spawn(mut command: Command) -> io::Result<(Child, Guardian)> {
    let parent_pid = std::process::id() as libc::pid_t;
    // Only async-signal-safe syscalls execute between fork and exec. The parent
    // check covers an abrupt desktop exit immediately before prctl.
    unsafe {
        command.pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM, 0, 0, 0) == -1 {
                return Err(io::Error::last_os_error());
            }
            if libc::getppid() != parent_pid {
                libc::raise(libc::SIGTERM);
            }
            Ok(())
        });
    }

    let (result_sender, result_receiver) = mpsc::sync_channel(1);
    let (stop_sender, stop_receiver) = mpsc::channel();
    let worker = thread::Builder::new()
        .name("kat-core-guardian".into())
        .spawn(move || {
            // Linux associates PDEATHSIG with this thread, not the app as a
            // whole. Never spawn from a temporary Tauri/Tokio restart worker.
            if let Err(undelivered) = result_sender.send(command.spawn()) {
                if let Ok(mut child) = undelivered.0 {
                    let _ = child.kill();
                    let _ = child.wait();
                }
                return;
            }
            let _ = stop_receiver.recv();
        })?;
    let guardian = Guardian {
        stop: stop_sender,
        worker: Some(worker),
    };
    let child = result_receiver
        .recv()
        .map_err(|_| io::Error::other("KAT Core launch worker exited unexpectedly"))??;
    Ok((child, guardian))
}

impl Drop for Guardian {
    fn drop(&mut self) {
        let _ = self.stop.send(());
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
