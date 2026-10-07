# KAT

A local-first Windows AI assistant foundation: persistent text chat, a local authenticated Core, a typed desktop interface, and approval-controlled tools.

This release supports OpenAI-backed conversation, session history, local time, and opening registered applications. It does not include voice, autonomous background work, connected services, browser automation, or arbitrary shell execution. See [product scope](docs/PRODUCT.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), [decisions](docs/DECISIONS.md), and [roadmap](docs/ROADMAP.md).

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

Install Python 3.12+, Node.js 24 LTS (22.12+ is also supported), Rust stable (1.90+), Microsoft C++ Build Tools with the **Desktop development with C++** workload and a Windows SDK, and the Microsoft Edge WebView2 runtime. The standard Tauri Windows prerequisites apply. Use a PowerShell terminal that can find `python`, `node`, `npm`, and `cargo`.

```powershell
git clone https://github.com/Google-Stein/KAT.git
cd KAT
Copy-Item .env.example .env
# Edit .env locally: set OPENAI_API_KEY to your own key. Never commit it.
.\scripts\setup-windows.ps1
.\scripts\dev-windows.ps1
```

Development starts Vite and Tauri. Tauri launches the Core virtual environment, waits for its authenticated health check, and opens the window. The repository `.env` is explicitly loaded for development. Existing process environment values take precedence. Provider/model changes are available in Settings; keys are configured outside the UI in this version. Restart the desktop after changing the key. `KAT_OPENAI_API_KEY` is a supported alias and takes precedence over `OPENAI_API_KEY`; cloud proxy bindings use this alias because the platform reserves the `OPENAI_` prefix.

If PowerShell blocks local scripts, use the policy approved for your machine; for example, `powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1` runs that single local script without changing the machine policy.

To try the tools, ask "What time is it here?" or "Open Notepad." Review the application ID in the approval card and select Allow or Deny. Only applications shown in Settings are available. Tool outcomes are recorded in the transcript and Audit screen. Approval executes the action; the next chat turn lets the model discuss its result.

## Windows production build

```powershell
.\scripts\build-windows.ps1
```

This locks dependency installation, packages Core with PyInstaller, bundles it as a Tauri resource, and builds the desktop/NSIS installer. The release key is supplied via the launched desktop's environment; it is never embedded in the executable. Development `.env` is not bundled. Release builds are currently unsigned.

For an executable-only build and startup smoke check:

```powershell
.\scripts\build-windows.ps1 -NoBundle
.\scripts\smoke-windows.ps1
```

Close a manually running Core/desktop first: the desktop owns port 42800 and refuses to attach to an unrelated process. Windows release builds and launch checks must run on Windows. GitHub Actions includes a Windows build and startup job; a configured workflow is not evidence that it has run.

## Standalone Core and browser development

`uv` is the dependency/virtual-environment manager. Install it from its official distribution if it is not available. From the repository root:

```bash
uv sync --project core --frozen --group dev
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

Missing `OPENAI_API_KEY` does not prevent browsing stored sessions/settings. Sending a message returns a clear configuration error until a key is configured. Network failures do not produce fake assistant replies.

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
- **Provider not configured:** set `OPENAI_API_KEY` in the development `.env` or desktop process environment, then restart. Settings reports configuration presence, not account validity.
- **Provider request failed:** confirm key validity, model availability, account quota, and HTTPS access to `api.openai.com`. Check the local audit/error code. Raw provider exceptions are not exposed because they may contain sensitive diagnostics.
- **Core unavailable:** run the standalone CLI to inspect startup output; confirm dependency setup and port 42800 availability. Tauri reports its Core startup failure instead of opening a disconnected chat.
- **Application unavailable:** choose an ID from Settings. No arbitrary executable path or shell command is supported. Application launch is Windows-oriented; other hosts advertise only supported registrations.
- **Approval after restart:** pending requests are retained. Claimed actions with uncertain outcomes are not automatically replayed. Inspect Audit before requesting the action again.
- **Native build fails:** check Rust/MSVC/Windows SDK and WebView2 prerequisites. On Linux, check the GTK/WebKit development libraries. Re-run setup using the committed lockfiles.
- **401/403 in browser development:** use the current standalone token, the exact allowed development origin/loopback URL, and avoid using a token from a previous desktop process.

For measured results from this implementation environment and unverified external checks, see [validation](docs/VALIDATION.md). Next implementation milestones are [Windows release hardening, conversation lifecycle, and provider/tool extension contracts](docs/ROADMAP.md).

## Trusted application configuration

Windows defaults register Notepad and Calculator when their system executables exist. A trusted owner can replace that list with `KAT_APPLICATION_ALLOWLIST_JSON`, a JSON array of objects with `id`, `label`, an existing absolute `executable`, and optional fixed `arguments`. For example, `[]` disables all application launching. This is configuration outside the model/API, not a way for the model to register executables. Restart Core after changes. Shells, interpreters, scripts, and network paths are rejected; Windows registrations must resolve to native `.exe` files. Only IDs reach the model and approval UI. Treat custom registrations as executable capabilities: choose harmless applications and bounded arguments.
