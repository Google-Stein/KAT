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

## 0.1.1 installed-application checkpoint

[Run 37730853420](https://github.com/Google-Stein/KAT/actions/runs/37730853420)
completed with **Core, desktop and Windows all successful**, on source `f085422`.
Windows packaging/tests used **CPython 3.12.10**. This supersedes the foundation's
portable-only installer limitation for the scenarios measured below.

| Executed check | Actual outcome |
| --- | --- |
| Locked Python tests, Ruff, format, mypy; actual Core startup/auth/persistence | Linux 92 passed; checks passed |
| Frontend tests, ESLint, Prettier, TypeScript, Vite | 25 passed; checks passed |
| Windows NSIS build and portable GUI smoke | Passed; real window, direct authenticated packaged child, 401 without bearer, owned listener |
| `smoke-installed-windows.ps1` | Passed current-user silent install into a path containing spaces, installed GUI/Core startup, normal and forced close, persisted conversation relaunch, uninstall retaining intact SQLite |
| Windows Python tests / packaged Core smoke | 91 passed, 1 POSIX skip; smoke passed |
| Windows native unit / explicit integration tests | 21 passed, 5 deliberate ignores; all 3 explicit integrations passed |
| Actual Windows Credential Manager synthetic entry | Native write/read/replace/remove passed; no owner credential touched |
| Installer/executable/diagnostic uploads | All passed; installer artifact 11530166466, executable 11530080926, diagnostics 11529589853 |

Installed normal startup used desktop PID 2964 / Core PID 8196; forced-stop startup
used 7028 / 9952. Relaunch checks used 5820 / 5068 and 3760 / 8228. Each window
existed, native authenticated health passed, unauthenticated health returned 401,
and both Core/listener disappeared at shutdown. Uninstall retained an integrity-
checked conversation database.

The owner reports personally exercising live OpenAI conversation, time, Notepad
approval/launch, provider errors and persistence on 0.1. This is **owner-reported
manual evidence**, not an agent-run live account test. No live OpenAI credential
is available in this cloud task. Native vault tests and SDK protocol simulations
are separate from interactive key-entry/account validation. Installer signing,
auto-update and upgrade UX remain future hardening. A later real local-inference
and installed-WebView gate will be reported separately when it actually passes.


## 0.2 real backend investigation — release gate still pending

[Run 37732000562](https://github.com/Google-Stein/KAT/actions/runs/37732000562),
source `9f2a98e`, passed Core and desktop checks, Windows packaging, portable
startup, installed native lifecycle and restart persistence. Its explicitly
downloaded official Ollama **0.40.1** runtime passed the pinned asset SHA-256;
Ollama verified the **Qwen3:1.7b** weights digest. On the actual Windows CPU runner,
`smoke-local.py` passed real local conversation, model-selected current-time tool,
and a model-requested Notepad approval/native launch through production Core with
no OpenAI key and a guard preventing any OpenAI client construction.

The installed-WebView automation then failed at `installed-startup`: CDP could
not attach within the existing 45-second deadline. This is **not a green 0.2
release gate**, and the real Core/backend successes do not certify the installed
UI journey. No startup timeout was increased. A separate released-application
attachment diagnostic isolates this test-automation issue from inference and
native packaging. GPU/RTX 4090 performance and a live OpenAI account are not
covered by the CPU/transport tests.

Release [v0.1.1](https://github.com/Google-Stein/KAT/releases/tag/v0.1.1) includes
the exact successful installer and SHA256SUMS. [Publication run 37732444023](https://github.com/Google-Stein/KAT/actions/runs/37732444023)
verified tag/source equality and all three green jobs before attaching artifact
11530166466. This avoids a cloud-side `uploads.github.com` network restriction;
no additional repository credential was needed. A duplicate tag-triggered
foundation workflow was canceled after the same source's successful main-branch
validation; future CI checks run on main pushes and pull requests.


The CDP failure reproduced on the already released 0.1.1 installer in diagnostic
runs 37733135360 and 37733439890, including an isolated WebView profile: connection
was refused on port 9527 while native logs confirmed window/Core readiness. No
production devtools/security settings were changed. Windows accessibility
attachment passed in [run 37733654761](https://github.com/Google-Stein/KAT/actions/runs/37733654761).
[Run 37734110569](https://github.com/Google-Stein/KAT/actions/runs/37734110569)
then exercised the actual released installed 0.1.1 UI's native masked dialog:
cancel, save synthetic key, replace synthetic key, close/relaunch with the vault
entry available to Core, and remove through Settings with Core/token refresh.
All passed. This extends 0.1.1's actual credential UX evidence; it is still not a
live account/billing test. The full 0.2 gate now uses normal Windows accessibility
with read-only inspection of its disposable test database; no CDP/debugging port
or production test command is introduced. Superseded CDP full runs were canceled
after this diagnosis rather than retried without a changed hypothesis.

## 0.2 installed local-inference release gate — passed

[Run **37737345322**](https://github.com/Google-Stein/KAT/actions/runs/37737345322)
completed at **2026-10-08 06:31:23 UTC**, source
**`54b4a54cc51290afee07a60cd492b9bd793477d9`**. **Core, desktop and Windows
all passed.** This establishes the 0.2 installed/local-inference milestone.
The earlier sections record historical foundation results; the current milestone
counts and commands are below. Final bounded UI polish uses the authenticated Core
version and saved provider for display. The release publication workflow requires
all three jobs to pass again on the exact final tagged source and publishes only
that run's installer. See the release notes for that final run.

| Actual command/check | Result |
| --- | --- |
| `uv sync --project core --frozen --group dev` | Locked installs passed; Linux Python 3.12.14 and Windows 3.12.10 |
| `uv run --directory core pytest tests ../tests/integration -q` | **139 passed** in Linux/cloud; SDK mocked HTTP and local mock transport remain deterministic tests |
| Core Ruff check / format / strict mypy | All passed; 16 typed source modules |
| `python scripts/version.py --check` | Passed; root VERSION is 0.2.0, generated Python/npm/Cargo/Tauri metadata agrees |
| `python scripts/smoke-core.py` | Passed actual process/auth/401/missing-key/persistence/restart/close |
| `npm ci`, `npm test`, ESLint, Prettier, TypeScript, Vite | **26 frontend tests passed**; all checks/build passed |
| `npm audit --audit-level=high` in cloud | Passed, zero reported vulnerabilities |
| Linux native unit tests / formatting | **20 passed, 4 deliberate ignores**; formatting passed |
| `scripts/build-windows.ps1 -PythonExecutable <setup-python executable>` | Real current-source desktop + PyInstaller Core + NSIS installer passed, CPython **3.12.10 x64** |
| `scripts/smoke-windows.ps1` | Real window, exact owned packaged child/listener, native authenticated health, 401 without bearer, normal/forced cleanup all passed |
| `scripts/smoke-installed-windows.ps1 -LocalInference` | Current-user install into a path with spaces, installed lifecycle, persistence, actual UI/local inference and uninstall all passed |
| `scripts/test-local-windows.ps1` / `smoke-local.py` | Actual Ollama **0.40.1**, SHA-256-verified official runtime; digest-verified **Qwen3:1.7b** weights; real Windows CPU conversation/time/approved native Notepad all passed, no OpenAI key/client use |
| `scripts/smoke-installed-ui.py` against installed production WebView | Native key cancel/save/replace, restart persistence and removal passed; local selection/readiness/save, greeting/time, Notepad UI approval, actual Notepad window and close/relaunch persistence all passed |
| Windows Python unit/integration tests | **138 passed, 1 POSIX execute-bit skip** |
| Windows packaged `smoke-core.py --executable .../kat-core.exe` | Passed actual authentication/keyless error/persistence/restart/close |
| Windows native unit tests | **21 passed, 5 deliberate ignores**; includes actual synthetic Credential Manager write/read/replace/remove, descendant containment and approved breakaway |
| Windows native tests with `--ignored --skip sleeper_fixture --skip launcher_fixture --test-threads=1` | All **3 explicit Core integrations passed** |
| `tests/integration/test_windows_smoke_diagnostics.ps1` | All **13 diagnostics checks passed**; PowerShell syntax separately passed in cloud |
| Installer / executable / diagnostic artifact uploads | Passed: **11532656974 / 11532801078 / 11532283777** |

The installed test uses production controls and the native masked credential
prompt. React never receives either fixture key. Inspection of its isolated
SQLite database is read-only: provider/settings/chat/approval mutations occur
through the UI. A real Notepad window opens only after the Allow once action,
survives normal KAT close, and is then closed by the test. Normal and forced
termination independently stop Core and release port 42800. Relaunch preserves
local provider/model, conversation and audit. Uninstall removes the application
while retaining an integrity-checked database; no owner data or credential is
modified by the disposable CI account.

Additional cloud checks passed: full Linux native build/Clippy and full Windows
MSVC-target/all-targets compile/Clippy (`--features tauri/custom-protocol`, warnings
denied); all 3 explicit native packaged/development/restart-worker integrations;
Ruff/format including scripts/integration files; regenerated actual Linux
PyInstaller Core (`--collect-all agents --collect-all openai --collect-submodules
uvicorn --recursive-copy-metadata openai-agents`), packaged process smoke and
standalone process smoke. The local route rejects cloud-backed Ollama metadata
before sending context, rejects remote endpoints/redirects/proxies, and never
constructs a cloud client on failed local requests. Audit/log redaction tests cover
secret-bearing raw SDK diagnostics and rejected arbitrary tool-name text.

### Installed-test investigation and fixes

Runs 37734328219 and 37735460406 passed backend inference and credential UI but
failed locating the offscreen provider selector. Actual accessibility diagnostics
showed Provider and Model as **ComboBox** controls; the model's HTML datalist is
not an Edit control. After removing a key, Settings remains scrolled down. The
library's default visible-only lookup filtered out offscreen controls before they
could be scrolled. The harness now resolves offscreen controls explicitly and
scrolls the real pane through normal mouse input. Startup timeout stayed 45 seconds.

Focused runs 37736422973 / 37736746052 isolated that lookup and the chat transition.
The session row can be committed before React mounts its composer, so selecting
the first Edit control raced with Settings. The harness now waits for the named
Message KAT input and a new session ID. It waits for a stored reply and enabled
composer after sending; Send correctly remains disabled when the draft is empty.
[Focused run **37737115074**](https://github.com/Google-Stein/KAT/actions/runs/37737115074)
passed the entire actual UI/local-model journey on the earlier packaged artifact.
The subsequent full run above rebuilt and installed current source and passed all
gates. These were harness corrections; debugging ports and relaxed production
security were never introduced. Successful native dependency builds are cached
before runtime checks; current application resources are always cleaned/rebuilt.

### Remaining manual limits

No agent-run live OpenAI account/billing test occurred; the owner-reported 0.1 live
test remains distinct from SDK transport tests and synthetic key UX. RTX 4090 GPU
performance and the recommended Qwen3:8b model remain owner-hardware checks; actual
CI used a small CPU model. Cloud-machine Ollama registry access was denied, so
real inference evidence comes from the Windows runner, not an invented Linux/GPU
result. Release installers remain unsigned, automatic updates are absent, and
interactive upgrade UX is not certified. Local SQLite/backups are not encrypted
by KAT. No semantic memory has been implemented; review the memory proposal first.

## 0.2.1 stale-tool-context hotfix — Windows gate pending

The owner reported a repeated 09:54 answer with no second `get_local_time` request.
The new deterministic HTTP-protocol regression reproduced that stale answer on
both OpenAI Agents SDK and Ollama before the fix (two expected failures). Promoting
persisted tool messages into user text exposed old outcomes without their matching
assistant tool calls. The shared history builder now omits those records from
future inference; active loop results, SQLite, approval cards, transcript and audit
are preserved. Shared instructions require new time/action calls on new requests.

The owner checked the failed Calculator attempt's Activity/approvals and reported
**no Calculator tool request**. That attempt was a model-selection failure, not an
observed Windows launcher failure. Tests now cover Calculator after earlier time
and Notepad activity and repeated Calculator requests. The production allowlist,
fixed native `.exe` launch, shell restrictions and approvals are unchanged.

Cloud checks passed: **146 Python tests**, including both actual provider wire
protocol regressions with mocked model decisions, Core Ruff/format/strict mypy,
version metadata consistency, real standalone Core authentication/persistence/
restart/shutdown, **26 frontend tests**, ESLint/Prettier/TypeScript/Vite build,
**20 native unit tests** (4 deliberate integration/fixture ignores), full native
Clippy with warnings denied, and all **13 PowerShell diagnostic checks**.
The installed Windows gate is being extended to assert two identical time
requests produce distinct newer results, two identical Notepad requests create
distinct approvals/windows, and Calculator selection/approval/native window
creation. Real Ollama Core validation also repeats Calculator. Deterministic
transport tests are not live local-model validation. Release/tag publication must
wait for a successful current-source Core, desktop and Windows workflow.
