# KAT

A local-first Windows AI assistant foundation: persistent text chat, a local authenticated Core, a typed desktop interface, and approval-controlled tools.

This release supports explicit OpenAI or local Ollama conversation, session history, explicit personal/project memory, local time, and opening registered applications. It does not include voice, autonomous background work, connected services, browser automation, or arbitrary shell execution. See [product scope](docs/PRODUCT.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), [decisions](docs/DECISIONS.md), and [roadmap](docs/ROADMAP.md).


## Explicit memory (0.3)

Open **Memory → Add memory**, or choose **Remember** beneath a user/assistant
message. Review the wording, kind and scope, then **Confirm & save memory**.
Typing “remember” in chat alone never creates a record. No model is needed to save.

Retrieval starts **off**. Enable **local memory retrieval** in Memory, select
**Local · Ollama**, then ask a related question in a new conversation.
For example, save “KAT should prefer local models when practical.”, restart KAT,
and ask “Do I prefer local or cloud models for KAT?” The response's expandable
**Memories used** lists the records and revisions inserted into that turn.

Memory supports search, project scopes, edits/revisions, pins, explicit
supersession, outdated/review status, source links, where-used links and forgetting.
Create minimal project scopes in Memory and select one in a conversation.
FTS5 lexical retrieval uses up to four relevant whole records within a 4,000-character
serialized budget; there are no embeddings and unrelated queries may return zero.

Memory is local SQLite storage, **not encrypted by KAT**. Never store credentials
or highly sensitive information. OpenAI receives no memory records; its ordinary
selected chat history may already contain the same information. Forget removes
current/revision/search wording, **not original transcripts or older backups**.
No automatic extraction, planning, scheduling or autonomy was added.
See [validation](docs/VALIDATION.md) for actual Windows/local-model results and
[the approved design](docs/MEMORY_DESIGN_PROPOSAL.md) for future boundaries.

## Installed application and local inference

Download an installer from [Releases](https://github.com/Google-Stein/KAT/releases)
or the `kat-windows-installer` artifact of a successful CI run. NSIS installs for
your current user; launch KAT from the Windows shortcut. No Python installation
or developer terminal is required. Uninstall preserves your database and vault
entry. Remove the saved key through Settings before uninstall if desired.

To run locally, separately install [Ollama](https://ollama.com/download/windows),
keep its server on loopback, disable its cloud features (`OLLAMA_NO_CLOUD=1` for the Ollama server), and explicitly install a local model:

```powershell
# Recommended starting point for RTX 4090 / 24 GB VRAM: ~5 GB weights.
ollama pull qwen3:8b
# Smaller CPU/CI smoke model, lower quality: ~1.4 GB weights.
ollama pull qwen3:1.7b
```

Choose **Local · Ollama** in KAT Settings, select an installed model, refresh status,
and save. Model discovery distinguishes an unavailable server from missing weights
and shows whether the model advertises tools. KAT never downloads weights or
starts/stops Ollama itself. GPU acceleration is Ollama's responsibility; check
`ollama ps` and its server diagnostics. RTX 4090 performance is not certified by
CPU CI. Normal KAT installation contains neither backend nor model weights.

Try “Hello, KAT.”, “What time is it?”, then “Open Notepad.” Approve the final action
through its card. Local failures stay local. To use cloud inference, explicitly
select OpenAI; its context and tool descriptions leave the device for OpenAI.

The explicit real-backend Core smoke command is:

```powershell
.\core\.venv\Scripts\python.exe .\scripts\smoke-local.py --model qwen3:1.7b
```

It requires an already running backend/model and on Windows tests repeated time,
Notepad and Calculator requests, each application launch after its own test approval.
`test-local-windows.ps1` is a disposable CI helper that explicitly
downloads a checksum-verified runtime (~1.47 GB) and weights (~1.4 GB).
`smoke-installed-ui.py` uses normal Windows accessibility and synthetic native
key input **only in a disposable Windows CI account**. It enables no debugging
port or developer tools. Deterministic
protocol tests do not count as real inference. See VALIDATION for measured gates.

`VERSION` is the release source; run `python scripts/version.py`, then `--check`.
Before a schema upgrade, restricted `.backup-vN-*` snapshots preserve committed
SQLite data including WAL. Stop KAT before manually restoring a backup. Older KAT
fails closed when opening a newer schema; do not replace the database with an empty
file to bypass this protection.

## Repository

```text
core/                    Python package, SQLite, FastAPI, Agents SDK adapter, tools, tests
desktop/src/             React chat, sessions, settings, approvals, audit UI
desktop/src-tauri/       Rust Core lifecycle, local authentication, desktop packaging
scripts/                 Windows setup/development/release helpers
tests/integration/       Cross-layer API and persistence checks
docs/                    Product, architecture, security, decisions, roadmap, validation
```

## Windows development

Install Python 3.12.x, Node.js 24 LTS (22.12+ is also supported), Rust stable (1.90+), Microsoft C++ Build Tools with the **Desktop development with C++** workload and a Windows SDK, and the Microsoft Edge WebView2 runtime. The standard Tauri Windows prerequisites apply. Use a PowerShell terminal that can find `python`, `node`, `npm`, and `cargo`.

```powershell
git clone https://github.com/Google-Stein/KAT.git
cd KAT
.\scripts\setup-windows.ps1
.\scripts\dev-windows.ps1
```

Development starts Vite and Tauri. Tauri launches the Core virtual environment, waits for its authenticated health check, and opens the window. The repository `.env` is explicitly loaded for development. Existing process environment values take precedence. Configure a local model or choose **Set API key** in Settings. Windows-native key entry stores the key in Credential Manager; saving/removing restarts Core automatically. React never handles provider keys. Environment/.env overrides are optional development configuration. `KAT_OPENAI_API_KEY` is a supported alias and takes precedence over `OPENAI_API_KEY`; cloud proxy bindings use this alias because the platform reserves the `OPENAI_` prefix.

If PowerShell blocks local scripts, use the policy approved for your machine; for example, `powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1` runs that single local script without changing the machine policy.

To try the tools, ask "What time is it here?" or "Open Notepad." Review the application ID in the approval card and select Allow or Deny. Only applications shown in Settings are available. Tool outcomes are recorded in the transcript and Audit screen. Approval executes the action and updates its card. Later model context excludes historical tool records and replaces their assistant replies with a result-free historical marker; every new action requires a fresh tool request and approval. Current tool-loop results still reach the model immediately.

## Windows production build

```powershell
.\scripts\build-windows.ps1
```

This locks dependency installation, packages Core with PyInstaller, bundles it as a Tauri resource, and builds the desktop/NSIS installer. Normal installed launch reads the current user's Windows Credential Manager entry. Keys are never embedded in the executable. Development `.env` is not bundled. Release builds are currently unsigned.

For an executable-only build and startup smoke check:

```powershell
.\scripts\build-windows.ps1 -NoBundle
.\scripts\smoke-windows.ps1
```

Close a manually running Core/desktop first: the desktop owns port 42800 and refuses to attach to an unrelated process. Windows release builds and launch checks must run on Windows. GitHub Actions includes a Windows build and startup job; a configured workflow is not evidence that it has run.

## Standalone Core and browser development

`uv` is the dependency/virtual-environment manager. Install it from its official distribution if it is not available. From the repository root:

```bash
uv sync --project core --python 3.12 --frozen --group dev
mkdir -p .local
uv run --project core python -m kat_core --env-file .env --data-dir .local/data --token-file .local/api-token
```

The service binds to `127.0.0.1:42800`. Its CLI creates a private token file when needed. If you supply `KAT_API_TOKEN`, use at least 32 non-whitespace random characters. Protect token files and `.env`; do not put them in shared directories. The desktop generates its own token, so standalone Core and desktop are separate launch modes.

In a second terminal:

```bash
cd desktop
npm ci
npm run dev
```

Open Vite locally and enter the standalone Core URL/token in the development connection screen. The token stays in memory and must be entered again after a reload. Browser mode is a development aid; the Windows deliverable is Tauri. Cloud onboarding does not provide a localhost web preview.

All API routes require Bearer authentication. A simple internal health check is:

```python
from pathlib import Path
import httpx

token = Path('.local/api-token').read_text().strip()
response = httpx.get('http://127.0.0.1:42800/health',
                     headers={'Authorization': f'Bearer {token}'})
response.raise_for_status()
print(response.json())  # contains status/configuration, never the token
```

No OpenAI key is needed for local Ollama inference or browsing history/settings. OpenAI conversation requires a configured key. Network failures do not produce fake assistant replies.

## Automated checks

From `core/`:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest ../tests/integration
```

From the repository root, `python scripts/smoke-core.py` verifies real process startup, authenticated HTTP, missing-key errors, restart persistence, and shutdown. `python scripts/smoke-core.py --executable PATH_TO_PACKAGED_CORE` also checks a PyInstaller build.

From `desktop/`:

```bash
npm test
npm run lint
npm run format:check
npm run typecheck
npm run build
cargo test --locked --manifest-path src-tauri/Cargo.toml --no-default-features
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo check --locked --manifest-path src-tauri/Cargo.toml
```

Python tests exercise API authentication, durable storage, provider integration contracts, tool validation, permission decisions, audit outcomes, and failures without contacting OpenAI. UI tests exercise chat/settings/approval interactions. Rust tests exercise process configuration and lifecycle helpers. `--no-default-features` isolates Rust lifecycle tests from the host GUI prerequisites; the normal native check still validates the desktop feature.

On Linux, Tauri additionally needs GTK3, WebKitGTK 4.1, an application-indicator development package, and a display. Debian/Ubuntu installation typically uses `libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev patchelf`. Linux builds are useful for development, but Windows remains the release target.

## Data, observability, and troubleshooting

- Standalone Core data defaults to `%LOCALAPPDATA%\KAT` on Windows and `$XDG_DATA_HOME/kat` (normally `~/.local/share/kat`) on Linux. Desktop-managed data uses `%LOCALAPPDATA%\com.kat.assistant` on Windows and `$XDG_DATA_HOME/com.kat.assistant` on Linux. `KAT_DATA_DIR`/`--data-dir` can override standalone storage.
- SQLite stores sessions, messages, settings, approvals, and audit events. API keys and bearer tokens are excluded. Back up with Core stopped; local data is not encrypted by this version.
- **Provider not configured:** select Local/Ollama or save an OpenAI key through the native Settings dialog. Settings reports key presence; a chat checks account validity. Optional environment overrides take precedence over the vault.
- **Local backend unreachable:** start Ollama on `127.0.0.1:11434` and refresh provider status. Do not expose it to your LAN.
- **Local model missing:** install the chosen model with `ollama pull MODEL`, then refresh. Downloads are explicit, can be several gigabytes, and are separate from KAT installation.
- **Local model cannot use tools:** choose a model advertising tool support; Settings identifies chat-only models. Text that looks like a tool call is never executed.
- **Provider request failed:** confirm key validity, model availability, account quota, and HTTPS access to `api.openai.com`. Check the local audit/error code. Raw provider exceptions are not exposed because they may contain sensitive diagnostics.
- **Core unavailable:** run the standalone CLI to inspect startup output; confirm dependency setup and port 42800 availability. Tauri reports its Core startup failure instead of opening a disconnected chat.
- **Application unavailable:** choose an ID from Settings. No arbitrary executable path or shell command is supported. Application launch is Windows-oriented; other hosts advertise only supported registrations.
- **Approval after restart:** pending requests are retained. Claimed actions with uncertain outcomes are not automatically replayed. Inspect Audit before requesting the action again.
- **Native build fails:** check Rust/MSVC/Windows SDK and WebView2 prerequisites. On Linux, check the GTK/WebKit development libraries. Re-run setup using the committed lockfiles.
- **401/403 in browser development:** use the current standalone token, the exact allowed development origin/loopback URL, and avoid using a token from a previous desktop process.

For measured results from this implementation environment and unverified external checks, see [validation](docs/VALIDATION.md). The next deliberate gate is [memory architecture review](docs/MEMORY_DESIGN_PROPOSAL.md); no semantic memory has been implemented.

## Trusted application configuration

Windows defaults register Notepad and Calculator when their system executables exist. A trusted owner can replace that list with `KAT_APPLICATION_ALLOWLIST_JSON`, a JSON array of objects with `id`, `label`, an existing absolute `executable`, and optional fixed `arguments`. For example, `[]` disables all application launching. This is configuration outside the model/API, not a way for the model to register executables. Restart Core after changes. Shells, interpreters, scripts, and network paths are rejected; Windows registrations must resolve to native `.exe` files. Only IDs reach the model and approval UI. Treat custom registrations as executable capabilities: choose harmless applications and bounded arguments.

## Supported Python runtime

KAT Core's language minimum is Python 3.12. KAT 0.1.x/0.2/0.3 development, tests and release packaging use **CPython 3.12.x exclusively**; later minor versions are not certified. Root and Core `.python-version` files select 3.12 for uv and GitHub Actions. Patch updates within 3.12 receive the same tests. CI passes the exact `setup-python` executable to Windows setup; local setup uses a matching PATH interpreter or `py -3.12`, never `py -3`. You can pass `-PythonExecutable C:\path\to\Python312\python.exe` to setup/build. An existing incompatible Core venv is rejected; remove only `core/.venv` and rerun setup to replace it. PyInstaller always runs through that validated Core venv, including with `-SkipSetup`.

A fully green Core, desktop and Windows workflow is required for every Windows release. The installed gate additionally exercises native credential entry, real local-model chat/tools, durable approval and data-preserving uninstall. `smoke-windows.ps1` verifies a real main window, native bearer-authenticated health evidence, unauthenticated rejection, exact parent/child/listener ownership, normal close cleanup and forced termination cleanup. It preserves diagnostics under `.local/windows-smoke`; CI uploads these even on failure. Native startup stages are recorded in `%LOCALAPPDATA%\com.kat.assistant\logs\desktop.log`, alongside `desktop-core.log` and `core.log`. Tokens are never included in these reports.
