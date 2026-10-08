# Validation record

Initial Linux validation ran in the Codex cloud workspace on 2026-10-07. The corrected packaged Windows runtime passed GitHub Actions on 2026-10-08; see the release-gate evidence below. No live OpenAI call was made: no provider key was present. The initial cloud network policy also denied HTTPS CONNECT to `api.openai.com`; GitHub Actions log access was subsequently configured and verified. SDK tests replace HTTP transport, not production permission/storage/orchestration logic.

## Toolchain and installation

Python 3.12.14, Node.js 24.19.0, npm 11.9.0, and Rust 1.99.0 were used. Python, JavaScript, and Rust dependency lockfiles are included. The existing Git repository and original CC0 license were preserved; no credentials or generated binaries were added to source control.

| Command / operation | Result |
| --- | --- |
| `uv sync --project core --frozen --group dev` | Passed; repeated locked installation |
| `npm --prefix desktop ci --cache /tmp/kat-npm-cache --no-fund --no-audit` | Passed; repeated locked installation |
| Official Rust installation into `/workspace/.kat-tools/` | Passed; TLS/artifact verification retained |
| Signed Debian APT update, download-only GTK/WebKit development dependencies, local extraction | Passed; no system package files changed |
| `git rev-parse --is-inside-work-tree` / status / ignore checks | Passed; only intended source/config/docs additions visible |
| `git diff --check` | Passed |

The initial default npm/uv caches were not writable; workspace/temporary cache locations corrected that. The initial UI dependency audit found vulnerable Vitest 3 development packages; the final locked Vitest 5.0.3 toolchain has zero reported advisories. The initial packaged Core omitted SDK dependency distribution metadata; recursive metadata collection corrected the actual startup failure.

## Python

Commands run from repository root unless noted. `UV_CACHE_DIR=/workspace/.cache/uv` was used in this sandbox.

| Command | Final result |
| --- | --- |
| `uv run --directory core pytest tests ../tests/integration -q` | **83 passed**, no skipped or expected-failure cases |
| `uv run --directory core ruff check . ../scripts/smoke-core.py ../tests/integration` | Passed |
| `uv run --directory core ruff format --check . ../scripts/smoke-core.py ../tests/integration` | Passed; 19 files |
| `uv run --directory core mypy` | Passed; 10 source modules, strict typing |
| `python scripts/smoke-core.py` | Passed; real CLI startup, authenticated API, unauthorized rejection, missing-key error, persisted session/settings after restart, shutdown |
| `python scripts/smoke-core.py --executable desktop/src-tauri/binaries/kat-core/kat-core` | Passed against actual PyInstaller distribution |

Eight cross-layer tests cover Host/Origin/auth boundaries, durable/repeated/concurrent approvals, error redaction, and actual SDK Responses protocol handling. The real Agents `Runner`, OpenAI Responses adapter, and `AsyncOpenAI` client run against a simulated HTTP transport, including function calls, returned results, pending approvals, malformed arguments, and unknown tools. They do not establish live model behavior, account access, quota, or provider availability.

## React / TypeScript

Commands run from `desktop/`.

| Command | Final result |
| --- | --- |
| `npm test` | **15 passed** across UI interactions and API-client checks |
| `npm run lint` | Passed; zero warnings |
| `npm run format:check` | Passed |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; production Vite assets produced |
| `npm audit --audit-level=high` | Passed; **zero vulnerabilities** reported, including development dependencies |

The UI checks cover sessions/chat, approval allow/deny, settings, audit, native recovery, request timeouts, redirect/remote-URL rejection, plain-text rendering, and failure paths. A successful chat whose sidebar refresh fails is not resubmitted automatically.

## Native desktop and packaging

Native validation uses the retained toolchain/local dependency prefix described below. Normal unit tests deliberately exclude subprocess fixtures and opt-in service integration tests; the three Core integration tests are run explicitly rather than counted as ordinary unit tests.

| Command / check | Result |
| --- | --- |
| `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features` | **8 unit tests passed**; 4 ignored by default (subprocess fixture and 3 explicitly executed service tests) |
| `cargo fmt --manifest-path desktop/src-tauri/Cargo.toml --check` | Passed |
| `cargo check --locked --manifest-path desktop/src-tauri/Cargo.toml` | Passed with full Linux desktop feature |
| `cargo clippy --locked --manifest-path desktop/src-tauri/Cargo.toml --features custom-protocol --all-targets -- -D warnings` | Passed |
| `cargo check --locked --manifest-path desktop/src-tauri/Cargo.toml --target x86_64-pc-windows-msvc --no-default-features` | Passed for Windows lifecycle/library code; no Windows linking or runtime claim |
| `KAT_NATIVE_TEST_REPO=/workspace/KAT cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features starts_real_core_and_releases_port -- --ignored --test-threads=1` | Passed; real owned development Core, authenticated health, unauthorized rejection, ephemeral token, port cleanup |
| `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features starts_packaged_core_and_releases_port -- --ignored --test-threads=1` | Passed against packaged Core |
| `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features core_outlives_short_lived_start_thread -- --ignored --test-threads=1` | Passed; retiring restart worker does not terminate owned Core |
| PyInstaller `--onedir` packaging with recursive SDK metadata | Passed; executable starts and serves actual Core API |
| `npm run tauri -- build --debug --no-bundle -- --locked -j 4` from `desktop/` | Passed; native window with production assets and packaged Core |
| Actual Tauri GUI under Xvfb with read-only library overlay | Passed startup and authenticated UI/Core connection; screenshot inspected |
| Real webview session creation and restart | Passed; created a session through the UI, restarted desktop/Core, and recovered it in the sidebar |
| Normal close and forced desktop exit on Linux | Passed; owned Core exited and listener closed |

The window rendered the chat workspace, local-connection indicator, session controls, settings/audit navigation, and truthful missing-key state. This is actual native UI rendering, separate from jsdom component tests. Cloud-local screenshots are retained at `.local/native-smoke/screenshot.png` and `.local/native-smoke/restarted-screenshot.png` and excluded from Git.

A lifecycle regression found during final validation was fixed: Linux's parent-death signal follows the process-creating thread, so a retiring restart worker could terminate Core while the desktop remained open. A dedicated creator guardian now survives for the Core process lifetime. Both a deterministic native test and an actual packaged-Core integration test verify that case. Windows uses its kernel Job Object instead.

## External checks and publication

- A native Windows build/run was **not executed** in this Linux machine. `.github/workflows/ci.yml` includes Windows packaging and `scripts/smoke-windows.ps1`, which checks a real window/owned Core, normal close, forced desktop exit, and Core port cleanup. That workflow has not been run or published by this task.
- A live OpenAI conversation was **not executed**. The uncredentialed connectivity probe failed at HTTPS CONNECT with HTTP 403. No TLS or verification bypass was attempted.
- Cloud configuration draft saving **succeeded** for `install_script`, `start_skill`, and a secure `KAT_OPENAI_API_KEY` requirement with destination `api.openai.com`; that destination was added to the saved network policy. No credential value was supplied. The platform reserves `OPENAI_` secret variable names, hence the supported alias.
- A draft save does **not** apply runtime networking/secrets or publish a snapshot. Review/save the environment settings, supply the key securely if live chat is needed, and publish the environment. New-task restoration has not been independently exercised.

## Prepared Linux native prerequisites

These flags apply only to this cloud machine's locally extracted Debian libraries. Standard Linux machines should install the documented Tauri prerequisites normally.

```bash
export CARGO_HOME=/workspace/.kat-tools/cargo
export RUSTUP_HOME=/workspace/.kat-tools/rust
export PATH="$CARGO_HOME/bin:$PATH"
export PKG_CONFIG_SYSROOT_DIR=/workspace/.kat-tools/apt/root
export PKG_CONFIG_PATH=/workspace/.kat-tools/apt/root/usr/lib/x86_64-linux-gnu/pkgconfig:/workspace/.kat-tools/apt/root/usr/share/pkgconfig
export LD_LIBRARY_PATH=/workspace/.kat-tools/apt/root/usr/lib/x86_64-linux-gnu
```

WebKit's helper executable paths are compiled into the Debian binary, so merely setting a library path does not enable GUI startup from a local extraction. Validation used a temporary read-only bubblewrap mount overlay for those paths, approved by the execution environment, with Xvfb. WebKit's sandbox remained enabled. The initial unprivileged namespace probe could not write its UID map; the approved restricted overlay succeeded without system-file writes. Startup recipes should preserve this isolation rather than patching libraries or disabling the sandbox.

The prepared overlay directory `/workspace/.kat-tools/namespace-libraries` has symlinks for system library entries pointing to `/run/kat-system-libraries/<entry>` plus a `webkit2gtk-4.1` link to the extracted WebKit helper directory. The successful launch used the following commands, with the bubblewrap command run under the execution environment's approved namespace permissions:

```bash
# Run Xvfb in a retained command session; stop only that session afterwards.
LD_LIBRARY_PATH=/workspace/.kat-tools/apt/root/usr/lib/x86_64-linux-gnu \
  /workspace/.kat-tools/apt/root/usr/bin/Xvfb :91 -screen 0 1280x900x24 -nolisten tcp -ac

# In a second session, from /workspace/KAT:
DISPLAY=:91 \
XDG_DATA_HOME=/workspace/KAT/.local/native-smoke/data \
XDG_CONFIG_HOME=/workspace/KAT/.local/native-smoke/config \
XDG_CACHE_HOME=/workspace/KAT/.local/native-smoke/cache \
LD_LIBRARY_PATH=/workspace/.kat-tools/apt/root/usr/lib/x86_64-linux-gnu \
bwrap --ro-bind / / --tmpfs /run \
  --ro-bind /usr/lib/x86_64-linux-gnu /run/kat-system-libraries \
  --ro-bind /workspace/.kat-tools/namespace-libraries /usr/lib/x86_64-linux-gnu \
  --bind /workspace /workspace --bind /tmp /tmp --dev-bind /dev /dev --proc /proc \
  -- dbus-run-session -- desktop/src-tauri/target/debug/kat-desktop

# Optional internal screenshot, from a third command:
DISPLAY=:91 import -window root .local/native-smoke/restarted-screenshot.png
```

No localhost preview link was created. Xvfb has no TCP listener; this is an internal test display, not a published application endpoint. Native/Core/Xvfb processes used in validation were stopped afterwards.

## Windows stabilization investigation

The first published workflow, [run 37693164653](https://github.com/Google-Stein/KAT/actions/runs/37693164653), tested foundation commit `f6292325f0172036bcb54f10e93ae1ccc5d432a8`. Core and desktop jobs passed. Windows packaging passed, but the desktop startup smoke failed; the original combined timeout gave no stage-specific diagnostics. This is a failed release gate, not Windows runtime validation. The owner reported that packaging selected Python 3.14.7 via `py -3` despite CI selecting 3.12. That runtime-selection defect is confirmed; its causal relationship to the startup failure remains under investigation.

Stabilization pins CPython 3.12.x, records native startup stages without secrets, verifies authenticated readiness evidence with exact process/listener ownership, and preserves CI failure logs. The 45-second desktop deadline remains unchanged. Local stabilization checks passed: 83 Python tests, 15 frontend tests, 9 native unit tests, 3 explicit native service integration tests, standalone and packaged Core restart smoke, Ruff/format/mypy, frontend lint/format/type/build, full Windows target compile check, native formatting and Clippy. Windows execution results will be recorded only after the corrected workflow actually runs.

The first stabilization run, [37718763734](https://github.com/Google-Stein/KAT/actions/runs/37718763734), confirmed packaging with Python **3.12.10**, 82 Windows Python tests passed and one POSIX execute-bit test skipped, packaged Core authenticated/persistence smoke passed, 8 Windows native unit tests passed, and 2 packaged native integrations passed. The development-launch integration failed port release. Investigation identified the Windows venv redirector descendant escaping the guard's silent-breakaway policy, plus a spawn-before-assignment race. The correction starts Core suspended, attaches it to a Job Object, then resumes its main thread. Ordinary Core descendants remain guarded; fixed, approved application launches alone explicitly request breakaway. Dedicated Windows descendant/approved-breakaway regression tests accompany the fix. This run did not reach desktop GUI smoke and does not satisfy the release gate.

Source investigation identified the packaged startup selection defect: Tauri CLI adds `tauri/custom-protocol` (a dependency feature), while KAT tested its own `custom-protocol` forwarding feature. Those flags need not be enabled together. The release therefore selected development Python, and the original smoke test required a `kat-core.exe` child. The correction queries `tauri::is_dev()` for both resource selection and development navigation access. The Python 3.14 selection was a separate confirmed build defect, rather than evidence that Python 3.14 startup duration caused the timeout.

[Run 37719602017](https://github.com/Google-Stein/KAT/actions/runs/37719602017) reproduced the topology defect on Python 3.12.10 and captured direct evidence: desktop PID 7708 launched `core/.venv/Scripts/python.exe` PID 10176; the actual API server ran as descendant PID 7540. Authenticated `/health` returned 200. The smoke failed explicitly with `[process-topology]` because there was no direct `kat-core.exe` child. Thus readiness duration was not the cause. Startup/Core logs were printed, exposed in check annotations and uploaded as `kat-windows-diagnostics` (artifact 11525585553). Core and desktop jobs passed; Windows remained failed pending the framework build-mode correction.

The isolated [Python 3.14.7 reproduction, run 37719666855](https://github.com/Google-Stein/KAT/actions/runs/37719666855), restored the original launcher and reproduced the same topology failure. Desktop PID 2360 launched venv Python PID 9472, whose server descendant PID 9376 returned authenticated health 200 in about three seconds. No packaged `kat-core.exe` was launched. This confirms the feature-flag/root-selection defect independently of the supported-interpreter correction; increasing the startup timeout would not repair it. This investigation branch is diagnostic evidence, not a supported Python 3.14 release configuration.

## Windows release gate: passed

[GitHub Actions run **37720158906**](https://github.com/Google-Stein/KAT/actions/runs/37720158906) completed successfully at **2026-10-08 03:02:42 UTC**, on source commit **`1d5a5014fc7db8a86cfbd9fc1ef8d8ab6104bd16`**. The **Core, desktop and Windows jobs were all green**. This satisfies the KAT 0.1 foundation's packaged Windows runtime gate. It does not certify a live model account or installer installation.

The Windows setup, Core venv, tests and PyInstaller packaging all used **CPython 3.12.10 x64**, selected explicitly from `actions/setup-python`; the packaging log confirms the same interpreter. The desktop deadline remained **45 seconds**.

| Command/check in the successful workflow | Actual result |
| --- | --- |
| `scripts/build-windows.ps1 -NoBundle -PythonExecutable <setup-python executable>` | Passed; actual Windows executable and bundled Core built |
| `scripts/smoke-windows.ps1` | Passed both real window/startup/authentication checks and both shutdown paths |
| `tests/integration/test_windows_smoke_diagnostics.ps1` | 13 checks passed across six failure categories, including clean and leaked lifecycle cases |
| `core/.venv/Scripts/python.exe -m pytest core/tests tests/integration -q` | **82 passed, 1 skipped**; skipped test checks the POSIX execute bit |
| `core/.venv/Scripts/python.exe scripts/smoke-core.py --executable desktop/src-tauri/target/release/binaries/kat-core/kat-core.exe` | Passed authenticated API, unauthorized rejection, keyless error, persisted session/settings after restart and shutdown |
| Windows `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features` | **10 passed**; 5 deliberately ignored (3 integrations and 2 subprocess fixtures) |
| Windows native tests with `-- --ignored --skip sleeper_fixture --skip launcher_fixture --test-threads=1` | **All 3 integration tests passed**: development Core, packaged Core and Core surviving a retiring restart worker |
| Windows `ordinary_core_descendants_cannot_escape` / `explicit_application_breakaway_survives` | Passed; descendants terminate and explicit application breakaway survives job close |
| Linux Core job: pytest, Ruff, formatting, mypy, real Core process smoke | **83 tests passed**; every other check passed |
| Desktop job: `npm test`, lint, format, typecheck, production build | **15 tests passed**; every other check passed |
| Desktop job: native tests and `cargo fmt --check` | **9 tests passed**, 4 intentional ignores; formatting passed |
| Windows diagnostic/executable artifact upload | Both passed |

The smoke's real process evidence was:

| Shutdown scenario | Desktop PID | Main window handle | Direct packaged Core PID / port owner | Authentication and cleanup |
| --- | --- | --- | --- | --- |
| Normal window close | 7592 | 393376 | 9064 | Native bearer-authenticated health passed; independent unauthenticated health returned 401; Core exited and port 42800 closed |
| Forced desktop termination | 7316 | 328026 | 4644 | Same authentication/ownership checks passed; killing desktop terminated Core through its Job Object and closed port 42800 |

Native logs confirm `core_start` selects `target/release/binaries/kat-core/kat-core.exe`. The smoke verifies the reported authenticated PID is exactly the desktop's single `kat-core.exe` child and the listener owner. Startup failures distinguish desktop-process, window-creation, core-child-startup, authenticated-readiness, process-topology and port-lifecycle. Core and desktop log tails appear in CI output and check annotations; diagnostics are retained on failure without environment or credential dumps.

Artifacts from this successful run:

- [Windows executable and bundled Core](https://github.com/Google-Stein/KAT/actions/runs/37720158906/artifacts/11525726081), artifact `11525726081`.
- [Windows startup diagnostics](https://github.com/Google-Stein/KAT/actions/runs/37720158906/artifacts/11526110519), artifact `11526110519`.

Additional cloud checks passed during stabilization: full native build and Clippy using the CLI's direct `tauri/custom-protocol` dependency feature; full Windows target/all-targets compile and Clippy checks; 9 local native unit tests and 3 explicit Core integrations; Python Ruff/format/mypy including smoke/integration files; standalone and packaged Linux Core restart smoke; frontend tests/lint/format/type/build; PowerShell parsing and all 13 diagnostic regression checks. These supplement the Windows run, rather than replacing it.

Remaining validation limits: live OpenAI access requires the owner's configured key; NSIS installation/uninstallation, signing, updates and manual Windows desktop usability testing were not exercised by this executable-only gate. Feature development remains paused; the unpushed credential-management work is preserved locally on `wip/windows-credential-setup` and is absent from these release corrections.
