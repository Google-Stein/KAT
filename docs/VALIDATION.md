# Validation record

## KAT 0.4 — bounded local capabilities

Baseline is released v0.3.1, source
`43bcdd8fc89e0c1239706e58f8b7446e8cce9d49`. The candidate adds weather,
system status and approved read-only roots; existing memory/provider/tool and
lifecycle gates remain mandatory. **Windows release validation is pending** until
the full exact-source workflow and installed real-Ollama sequence pass.

### Local checks

| Command/check | Actual result |
| --- | --- |
| `uv run --directory core pytest tests ../tests/integration -q` | **264 passed, one Windows-only sharing test skipped**; includes 44 executed capability tests, weather failures/freshness/compression/retry deadline bounds, strict fresh system selection, owner registration/catalog visibility, removal CORS/authentication, path attacks, metadata-only preflight/deadline failure, addressable listing paths, content approval/audit privacy and provider-independent dispatch |
| Core `ruff check`, `ruff format --check`, `mypy` | Passed; **31** typed source modules; installed-UI helper and SDK integration test also linted/formatted |
| `npm test` | **41 passed**, including explicit weather confirmation/native selection/Add and escaped text preview |
| `npm run lint`, `format:check`, `typecheck`, `build` | All passed; production frontend built |
| `cargo fmt --check`, `cargo test --locked --no-default-features` | Passed; **20 native tests**, four opt-in/fixture tests ignored |
| Linux and Windows-target `cargo clippy --locked --no-default-features -- -D warnings` | Passed; Windows target checks shared native code, including folder picker; actual full Windows application build remains a CI gate |
| `python scripts/version.py --check`, `git diff --check` | Passed; 0.4.0 manifests/locks synchronized |
| PyInstaller one-directory `kat-core` build | Passed with certified Python 3.12.14; includes psutil and existing Agents SDK |
| `python scripts/smoke-core.py`, same with `--executable desktop/src-tauri/binaries/kat-core/kat-core` | Both passed real startup, bearer-authenticated API, keyless failure, restart persistence and shutdown |
| Native `cargo test ... -- --ignored --skip sleeper_fixture --test-threads=1` with `KAT_NATIVE_TEST_REPO` | **3 real Core integrations passed**: development child, packaged child, worker lifetime and released port |
| PowerShell `tests/integration/test_windows_smoke_diagnostics.ps1` | **18 diagnostics passed** on PowerShell Core/Linux; actual Windows topology/lifecycle remains separately required |

The real Open-Meteo adapter resolved Thornton, Colorado and returned current
conditions through the cloud platform's HTTPS proxy. Direct DNS in this cloud
machine is unavailable; this experiment overrides only the test client's proxy
configuration. Production retains `trust_env=False`. It is external-provider
evidence, not installed Windows or offline validation. The saved environment
draft adds only the two weather destinations for future development.

### Windows installed acceptance — pending

Full [37907471638](https://github.com/Google-Stein/KAT/actions/runs/37907471638),
source `c5cdce1cc767278a3fb4ce5cd20b80edf47c3349`, passed Core/Desktop,
Windows tests/build/lifecycle and the installed name variants, preferences,
credentials, time/apps, two live weather lookups, RAM, native root Add, listing,
and approved exact file text with metadata-only audit. Traversal acceptance then
waited for an enabled composer despite Core completing the turn with HTTP 200.
The helper now inspects unexpected pending approvals directly and reports safe
tool-state metadata. Direct [37910175000](https://github.com/Google-Stein/KAT/actions/runs/37910175000)
submitted the original ambiguous traversal wording but the model listed the folder
instead; no traversal read reached Core. The guard check now explicitly proposes
literal JSON arguments and requires actual trusted rejection, without a substitute
file approval. UI entry escapes keyboard-control braces and verifies the persisted
user text exactly. The focused diagnostic workflow permits 25 minutes for the
observed CPU Core plus installed-UI sequence; the release job, startup, tool and
whole-turn limits are unchanged.

Focused [37911455573](https://github.com/Google-Stein/KAT/actions/runs/37911455573),
source `ef93d595504093cd412c72771b4d464838ca5fa8`, passed the entire direct
Qwen2.5:7b sequence with the explicit guard request. Actual audit contains
`read_text_file` / `tool_rejected` / `path_outside_root`; no approval or content
read was created. Earlier time/apps/name/RAM/listing/two-read assertions also
passed. Installed acceptance on a newly built exact-source installer is still required.

Full candidate [37901963119](https://github.com/Google-Stein/KAT/actions/runs/37901963119),
source `325601432ab0053478659daafc72168f0e6b3038`, passed Core/Desktop,
Windows unit/native tests, packaging and normal/forced lifecycle checks. Its real
installed Qwen2.5:3b sequence passed tools, preferences/revisions and the first
name question, then failed the second name answer despite correct ID/revision
retrieval. Focused [37905251404](https://github.com/Google-Stein/KAT/actions/runs/37905251404)
reproduced the answer "You are named KAT" for the disposable Luis memory.
Memory instructions now distinguish the human owner from the assistant's identity
and ask the model to answer factual questions from relevant supplied evidence.
Retrieval, the untrusted-data envelope, permissions and OpenAI exclusion are unchanged.
Both name variants are also required by the direct real-Ollama smoke test;
the full installed gate remains mandatory.

Clarifying identity alone did not make the 3B model reliable. Qwen2.5:7b answered
both names but exceeded the earlier 60-second inference request deadline at the
expanded file catalog. Actual backend logs measured about 20 prompt tokens/second.
The local request limit is now 90 seconds within the unchanged 120-second turn
limit. Focused [37906650795](https://github.com/Google-Stein/KAT/actions/runs/37906650795),
source `a4b653c0f8dde44367658d2eeab1eb5af57a6ea8`, then passed the full direct
Core/Ollama sequence: name variants, original tools, RAM, listing and two exact
file reads with distinct approvals and metadata-only audit. CI explicitly uses
Qwen2.5:7b; saved owner choices are unchanged. This is not installed release validation.

The extended production-UI helper requires real local Ollama, existing name-memory
and time/Notepad/Calculator regressions, explicit city confirmation, two fresh
external weather calls, fresh RAM metrics, native folder selection plus separate
Add, bounded listing, approval before exact disposable text is returned, audit
body exclusion, trusted traversal rejection and configuration after relaunch.
No owner files, fake weather or debug ports substitute for this gate.

The first full run [37883512682](https://github.com/Google-Stein/KAT/actions/runs/37883512682)
passed Core/Desktop and Windows packaging/window/lifecycle, then failed real local
Core inference: Qwen selected `get_local_time` with an extra string argument.
Focused diagnosis [37884336343](https://github.com/Google-Stein/KAT/actions/runs/37884336343)
confirmed the invalid argument shape without logging values. Strict validation
correctly prevented execution. Explicit parameterless-tool instructions and safe
declared-field guidance on rejection fixed the model call; no arguments are
silently discarded or coerced. The obsolete intermediate full run was cancelled.

Focused real Windows Core/Ollama run
[37884572448](https://github.com/Google-Stein/KAT/actions/runs/37884572448), source
`51d6251556646188a9cbc67f02475b2d58951f13`, passed actual conversation, two fresh
time results, two Notepad and two Calculator requests with distinct approvals,
allowlisted native executions and audit. OpenAI client construction was prohibited.
This focused gate is **not** a substitute for full installed acceptance.

Full run [37884571916](https://github.com/Google-Stein/KAT/actions/runs/37884571916)
passed the old installed credentials/tools/memory/name sequence and two real
external Open-Meteo lookups, then failed RAM tool selection: zero system results.
Focused [37885182044](https://github.com/Google-Stein/KAT/actions/runs/37885182044)
proved another extra string argument; Qwen repeated rejection text rather than
correcting its call. Explicit no-argument descriptions and one-correction guidance
still failed with four invented object arguments in
[37885466458](https://github.com/Google-Stein/KAT/actions/runs/37885466458).
The metrics API was not reached. Larger-model experiments did not resolve the
whole gate: [37885767794](https://github.com/Google-Stein/KAT/actions/runs/37885767794)
hit a bounded model timeout with hybrid Qwen3:4b (about eight tokens/second);
[37886629856](https://github.com/Google-Stein/KAT/actions/runs/37886629856) failed
Notepad selection with Qwen3:4b-instruct. No timeout or security boundary was relaxed.

The final interface exposes a strict bounded `metric` enum, returns only the
chosen category and fresh collection metadata, and advertises file tools only
after owner root registration in both adapters. Actual Qwen3:1.7b CPU run
[37887532151](https://github.com/Google-Stein/KAT/actions/runs/37887532151), source
`c475f94f0292db8533cbe4243e1983c006a7bb75`, passed original time/applications plus
fresh RAM collection at 2026-10-09 05:15:00 UTC (2026-10-08 23:15:00 America/Denver).
The CI recipe retains this small model. Saved owner choices never change.

Full [37887532043](https://github.com/Google-Stein/KAT/actions/runs/37887532043)
passed original installed tools/memory/name checks, then received a failed weather
provider result. Safe category/status diagnostics were added; the external
lookup and full installed acceptance remain gates, not assumed successes.

Fixed-provider timing diagnosis
[37889366804](https://github.com/Google-Stein/KAT/actions/runs/37889366804)
returned two actual Windows HTTPS 200 responses in 1,281 and 734 ms, with DNS
resolution in 16 ms. Intermittent transport timeouts therefore warrant one
bounded transport retry within the unchanged eight-second request budget,
not an increased startup timeout or cached weather. Full run
[37889718681](https://github.com/Google-Stein/KAT/actions/runs/37889718681)
passed existing installed memory/tools, two fresh weather lookups and RAM.
The second weather lookup recovered from a transport timeout through the bounded
retry. The test driver then failed immediately locating the native picker Edit
control; no completed file acceptance is claimed for that run. The harness now
selects a visible dialog, reports only control classes/IDs/visibility, and waits
for its field. Windows Core/path/native tests run before installed UI so a UI
failure cannot conceal their outcomes.

Run [37891098005](https://github.com/Google-Stein/KAT/actions/runs/37891098005)
passed actual Windows **260 Core/integration tests (one POSIX execute-bit skip)**,
**21 native tests** plus **three explicit Core integrations**, all 18 smoke
diagnostics and packaged normal/forced lifecycle checks. It was cancelled during
installed acceptance after a separate focused run identified a superseding test
driver correction. Focused picker diagnostics confirmed a real visible Edit and
OK control: a Win32 wrapper must use its child wrapper API, and edited shell paths
must be committed with real keyboard input. These partial results do not establish
a green release gate.

Focused native folder check
[37891913495](https://github.com/Google-Stein/KAT/actions/runs/37891913495)
passed: the actual native picker selects the disposable local folder, selection
alone creates no root, and the explicit Add control registers its verified path.
This uses the production UI and Core with no model, debug port or test IPC; it
isolates picker automation and does not replace installed real-Ollama acceptance.

Pre-release path review found that read-attributes-only Windows directory handles
do not enforce the intended sharing exclusion, and allowing write-sharing permits
in-place reparse changes before path-based enumeration. Directory pins now request
list-directory/read-attributes access and allow read-sharing only. A Windows-only
kernel regression verifies writes work outside the pin, fail with sharing error
32 while pinned, and rename is also denied. It does not replace existing junction,
alias, traversal, sibling-prefix and actual installed-root checks.

Run [37892660358](https://github.com/Google-Stein/KAT/actions/runs/37892660358)
passed the strengthened real Windows sharing regression within **261 tests and
one POSIX skip**, native tests/integrations, packaging and both lifecycle paths.
Installed acceptance stopped at the synthetic revised-memory answer assertion;
the correct current revision was selected. A bounded fixture-only answer diagnostic
was added. Earlier run
[37891913115](https://github.com/Google-Stein/KAT/actions/runs/37891913115)
passed actual folder registration/listing, then stopped before content access
because the proposed approved relative filename did not match the request.
The shared schema now explains root-relative filenames explicitly, and live Core
acceptance also requires two named-file reads with distinct approvals and exact
text/metadata-only audit. No incorrect pending file is approved by the test.

Focused Core/file run
[37898618452](https://github.com/Google-Stein/KAT/actions/runs/37898618452)
passed existing live model/time/apps/RAM, then correctly rejected root registration
from the runner's 8.3-aliased default TEMP path. Disposable live file fixtures now
use the canonical `RUNNER_TEMP` directory; production alias checks stay strict.

Focused picker run
[37898709617](https://github.com/Google-Stein/KAT/actions/runs/37898709617)
also passed against the rebuilt `b2b1ab8` Windows executable/Core: stronger actual
directory sharing permits ordinary native selection and explicit root registration.

Qwen3:1.7b repeatedly interpreted the friendly label as a path prefix; no incorrect
file was read. Metadata-only preflight now rejects missing targets before approval
and provides bounded recovery guidance. Listings provide exact usable relative
paths, excluding unsupported/overlength names instead of fabricating truncated
addresses. A preflight timeout fails closed with a sanitized audit category.

Actual Windows/local Core comparison
[37900903196](https://github.com/Google-Stein/KAT/actions/runs/37900903196), source
`909c100b7a95909a3b4b91e1f5fb0c4a02e7c3fb`, passed with **Qwen2.5:3b CPU**:
conversation, two new time calls, two Notepad and two Calculator approvals/native
executions, RAM, live directory listing and two exact named-file requests with
distinct approvals/returned text and metadata-only audit. The direct fixture
metadata probe also passed; no body was read before approval. Qwen3:1.7b failed
listing/relative-path selection in the equivalent run. The successful 3b model is
the new explicit CI recipe; no saved owner model or runtime deadline changes.
A subsequently dispatched 7b comparison was cancelled after the required smaller
model gate passed. These focused results still do not certify full installation.

### Limits

Open-Meteo is an external service under personal noncommercial upstream terms;
current conditions are model-derived weather data rather than local sensors.
System CPU model/GPU VRAM can be unavailable. Files are UTF-8 only, 64 KiB maximum
with 12,000 returned characters; listing/search have explicit bounds. There is no
body indexing, write access or automatic post-approval inference. Local transcript
and approval records retain text; audit does not. Failed OS calls may continue in
a worker after the API deadline. Same-user malware and manual SQLite modification
are outside KAT's isolation boundary. See [CAPABILITIES.md](CAPABILITIES.md).

## KAT 0.3.1 — memory retrieval quality

The baseline was published v0.3.0 source
`71e9336d48c5375a78d606bd01c315b68365b3f7`. Before implementation, the automated
new-conversation regression reproduced the owner's exact failure: persisted
“main user is named Luis” returned no record for “What is my name?”. The fix
uses SQLite Porter/unicode61 consistently in candidate search and relevance.
Migration 4 changes only the derived index; there is no owner-name branch,
embedding system, automatic extraction or expansion of tool permissions.

### Local checks

These ran in the Linux cloud workspace on CPython 3.12.14, Node 24.19.0 and
Rust 1.99.0 with existing locked dependencies. They do not certify Windows runtime
or the owner's RTX 4090. Historical sections below retain older release totals.

| Command / gate | Actual result |
| --- | --- |
| `uv run --directory core pytest tests ../tests/integration -q` | **220 passed**, including 39 new quality/index-migration checks and all existing privacy/tool-history regressions |
| Core `ruff check . ../scripts/smoke-installed-ui.py ../scripts/benchmark-memory.py`; `ruff format --check` on the same targets | Passed |
| Core `mypy` | Passed; strict checks over 22 source modules |
| `python scripts/version.py --check`; `git diff --check` | Passed |
| Desktop `npm test` | **35 passed** |
| Desktop `npm run lint`, `format:check`, `typecheck`, `build` | Passed; production assets built |
| Native `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features` | **20 passed**, four fixture/explicit integration tests ignored |
| Native `cargo fmt --check`; `cargo clippy --locked ... --all-targets --features tauri/custom-protocol -- -D warnings` | Passed |
| Native opt-in `--ignored --skip sleeper_fixture --test-threads=1` with `KAT_NATIVE_TEST_REPO` | **Three passed** against real development/current PyInstaller Core; ownership and port cleanup passed |
| CPython 3.12 PyInstaller `--onedir`, current Core and metadata | Passed |
| `python scripts/smoke-core.py`, then `--executable desktop/src-tauri/binaries/kat-core/kat-core` | Both passed actual startup/authentication/keyless errors/restart persistence/shutdown |
| PowerShell `tests/integration/test_windows_smoke_diagnostics.ps1` | **18 diagnostic checks passed**; Linux execution, separate from Windows acceptance |
| Existing `scripts/benchmark-memory.py`, 5,000 records / 100 iterations | Same-host query-pair baseline **0.592 ms median / 0.763 ms p95**, after **1.504 / 1.981 ms** |

The quality matrix passes all six requested examples: both name inflections,
model setup preference, local inference preference, active-project focus and
concise response style. It also covers alternate owner names, other domains,
accents and literal Unicode. Weather/name, cooking/model, generic-only words,
unrelated pins, hostile FTS text and wrong-project cases abstain. Candidate reads
remain at most 50; output remains at most four records / 4,000 serialized characters.

Representative schema-3 data, revisions, usage, projects, settings, pending approvals,
audit and transcripts remain identical after upgrade; WAL-inclusive backup retains
the original index/data. Failed migration restores actual old postings and version.
Forget removes stemmed search artifacts. Safe diagnostics expose counts, selected
ID/revision pairs and duration without query/private candidate wording. Synthetic
HTTP tests exercise the actual Ollama adapter across restart/new sessions; they
are protocol regressions, not real-model validation. Existing OpenAI SDK exclusion,
prompt-injection/approval, scope and fresh time/Notepad/Calculator tests all pass.

Lexical limits remain: car/automobile, some irregular forms such as focus/focused,
and extra unmatched query words can miss; sparse universe/university stems can
collide. Conservative multiword gating rejects the tested campus/universe query,
but does not claim semantic disambiguation. Continue owner relevance testing before
considering embeddings. Benchmark numbers measure the matching + unrelated query
pair, not inference/GPU latency; the roughly 0.9 ms median increase is documented.

### Windows installed acceptance — passed

[Full CI **37875546219**](https://github.com/Google-Stein/KAT/actions/runs/37875546219)
passed **Core, desktop and Windows** for source
`4f8c49a89e1aa505fa500ac6e0c9877d5802eed4`. Windows completed on **2026-10-08
at 20:45:26 America/Denver** (2026-10-09 02:45:26 UTC). These are actual Windows
runtime, installation, accessibility and local-inference results.

| Windows command / gate | Actual result |
| --- | --- |
| `scripts/build-windows.ps1 -PythonExecutable <setup-python executable>` | **CPython 3.12.10 x64**, current PyInstaller Core, desktop and `KAT_0.3.1_x64-setup.exe` passed |
| `scripts/smoke-windows.ps1` | Actual window, authenticated owned Core, independent unauthorized **401**, single owned listener; normal close and forced desktop termination stopped Core and released **42800** |
| `scripts/smoke-installed-windows.ps1 -LocalInference` | NSIS current-user install into a path with spaces, installed lifecycle/relaunch, real local Core/UI/tool/memory checks and uninstall/data preservation passed |
| `scripts/test-local-windows.ps1` / `smoke-local.py` | Checksum-verified **Ollama 0.40.1 / Qwen3:1.7b CPU**; no OpenAI key, fresh time twice, distinct Notepad/Calculator selections, approvals, executions and audit passed |
| `scripts/smoke-installed-ui.py` | Native key entry/cancel/save/replace/restart/remove using synthetic credentials; real chat, fresh time twice, two Notepad approvals/windows and Calculator approval/window passed; approved apps survived KAT close |
| Installed memory UI sequence | All original create/enable/restart/retrieve/revision-2 edit/Forget/zero-usage/Remember/source navigation checks passed, followed by the name-recall sequence below |
| `core/.venv/Scripts/python.exe -m pytest core/tests tests/integration -q` | **219 passed, 1 skipped** (POSIX execute-bit check); actual Windows quality and index migration tests passed |
| `scripts/smoke-core.py --executable <packaged kat-core.exe>` | Actual authentication/keyless errors/restart persistence/shutdown passed |
| Windows native ordinary `cargo test --locked ... --no-default-features` | **21 passed**, five fixture/explicit integration tests ignored |
| Windows native `--ignored --skip sleeper_fixture --skip launcher_fixture --test-threads=1` | All **three** real-Core lifetime/packaging integrations passed |
| `tests/integration/test_windows_smoke_diagnostics.ps1` | **18 checks passed**; unchanged readiness deadline, distinct failures and transient probes |
| Installer/executable/diagnostics uploads | All passed |

The new owner regression passed through production UI controls, with read-only
database assertions and real Ollama replies:

1. With retrieval explicitly enabled, review/confirm **“main user is named Luis”**
   using Add memory. Close and relaunch the installed KAT.
2. Start a **brand-new empty conversation** and ask **“What is my name?”**.
   Ollama answers **Luis**; exactly one usage link references the confirmed record
   at revision **1**. Expand **Memories used · 1** and verify the stored wording.
3. Start **another empty conversation**, ask **“What am I named?”**, and verify
   the real name answer, same correct ID/revision and visible response inspector.
4. Start another conversation and ask **“What is the weather in Oslo?”**.
   No name or other memory is selected: usage is zero and no memory inspector appears.

No CI failure or timeout change was required for this hotfix. The exact public
tag must also pass full CI **after this results-documentation commit**. Release
notes link that final run; publication rejects any tag/source mismatch and uploads
only its validated installer plus SHA256SUMS. The first green run above provides
this record's actual evidence, not authorization to skip checks on later source.
Owner RTX 4090 performance, larger models and ongoing real-world relevance remain
owner testing; they are not certified by hosted CPU CI.

## KAT 0.3 — bounded explicit memory

The implementation was reconciled with published v0.2.1 commit
`c870111b813a3d1ba5b28b2a4bbac164d6f0f076`. Owner approval covers explicit memory
only. Automatic extraction, embeddings, cloud injection, planning and autonomy
remain unimplemented. The sections below this 0.3 record preserve historical
release evidence and are not current test totals.

### Local checks

Commands ran in the Linux cloud workspace with CPython 3.12.14, Node 24.19.0,
Rust 1.99.0 and committed Python/npm/Cargo locks. Windows packaging uses the exact
GitHub Actions CPython 3.12.10 executable, not `py -3`.

| Command / gate | Result |
| --- | --- |
| `uv run --directory core pytest tests ../tests/integration -q` | **181 passed**, including 33 new memory checks and all prior tool-history/security regressions |
| `uv run --directory core ruff check .` and changed Python acceptance/benchmark scripts | Passed using Core's lint configuration |
| `uv run --directory core ruff format --check .` and changed scripts | Passed |
| `uv run --directory core mypy` | Passed; strict typing, 21 source modules |
| `python scripts/version.py --check`; `git diff --check` | Passed |
| Desktop `npm test` | **35 passed** |
| Desktop `npm run lint`, `format:check`, `typecheck`, `build` | Passed; production frontend assets built |
| `cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --no-default-features` | **20 passed**, four ignored subprocess/explicit integration fixtures |
| `cargo fmt --manifest-path desktop/src-tauri/Cargo.toml --check` | Passed |
| `cargo clippy --locked --manifest-path desktop/src-tauri/Cargo.toml --all-targets --features tauri/custom-protocol -- -D warnings` | Passed with Linux GUI dependencies; Windows `x86_64-pc-windows-msvc` target also passed, not a local Windows runtime claim |
| Native opt-in `--ignored --skip sleeper_fixture --test-threads=1` with `KAT_NATIVE_TEST_REPO` | Three real Core integration tests passed, including current PyInstaller distribution and port cleanup |
| Current Linux PyInstaller build; `scripts/smoke-core.py` standalone and `--executable` packaged | Passed actual startup, authentication/unauthorized rejection, keyless error, restart persistence and shutdown |
| PowerShell `tests/integration/test_windows_smoke_diagnostics.ps1` | **18 diagnostic checks passed**; Linux PowerShell execution is separate from actual Windows lifecycle acceptance |
| `uv run --project core python scripts/benchmark-memory.py` | 5,000 synthetic records, 100 iterations: matching + unrelated query combined **0.603 ms median / 0.873 ms p95**, at most 50 candidates per query |

Retrieval measurements are not inference/GPU latency. Retrieval returns at most
four whole records within 4,000 serialized characters, applies relevance and
scope/status/date filters and abstains when evidence is weak. No full-table
Python scan, embeddings or external search service is involved.

Core/integration tests exercise schema-2 upgrade preservation, WAL-inclusive
migration backup, atomic rollback, future-schema refusal, FTS rebuild, explicit
creation and source validation, project isolation, eligibility/relevance/budgets,
expiry/supersession, revision concurrency, secret rejection/redacted errors,
local-only context, prompt injection against actual tool permission boundaries,
cloud exclusion and no fallback, atomic reply/usage recording, forget including
revisions/search artifacts and forget during a model run. Cloud tests execute the
actual OpenAI Agents SDK/HTTP adapter with synthetic transport: memory payloads
are absent and usage is zero; normal transcript behavior is explicitly distinct.

Frontend tests cover review/cancel/confirm creation and Remember, retained failed
save drafts, provenance/unavailable sources, exact used revisions, escaping,
edit/revision history, pin/status, supersession, explicit Forget confirmation,
retrieval default/off/privacy notices and prior chat/settings/approval behavior.

### Windows installed acceptance

[Full CI **37853734500**](https://github.com/Google-Stein/KAT/actions/runs/37853734500)
passed **Core, desktop and Windows** on 2026-10-08 for source
`c33e42ae02022ac351c94ac5024518ad8331bb82`. Windows completed at
22:37:40 UTC. This is actual Windows execution, not cross-compilation or a mocked
model. The NSIS installer was built from current resources, installed into a path
with spaces, exercised, relaunched and uninstalled while preserving local data.

| Windows command / gate | Actual result |
| --- | --- |
| `scripts/build-windows.ps1 -PythonExecutable <setup-python executable>` | CPython **3.12.10 x64**; PyInstaller Core, native desktop and NSIS installer passed |
| `scripts/smoke-windows.ps1` | Real window, native authenticated readiness, independent unauthorized HTTP **401**, exactly one owned Core/listener; normal close and forced termination stopped Core and released port **42800** |
| `scripts/smoke-installed-windows.ps1 -LocalInference` | Installed lifecycle, relaunch persistence, real Ollama/Core/UI/tool/memory sequence and uninstall/data preservation all passed |
| `scripts/test-local-windows.ps1` / `smoke-local.py` | Actual **Ollama 0.40.1 / Qwen3:1.7b CPU**; real conversation with no OpenAI key; two fresh time results, separate Notepad and Calculator approvals/executions/audit |
| `scripts/smoke-installed-ui.py` via installed acceptance | Native credential cancel/save/replace/restart/remove with synthetic keys, actual UI chat, fresh time twice, Notepad twice and Calculator window; approved apps survive KAT close |
| `tests/integration/test_windows_smoke_diagnostics.ps1` | **18 passed**, including transient probes within the original deadline and distinct failure classifications |
| `core/.venv/Scripts/python.exe -m pytest core/tests tests/integration -q` | **180 passed, 1 skipped**: POSIX execute-bit check is inapplicable on Windows |
| `scripts/smoke-core.py --executable <packaged kat-core.exe>` | Actual packaged CLI/authentication/keyless error/restart persistence/shutdown passed |
| Windows `cargo test --locked ... --no-default-features` | **21 passed**; five fixture/opt-in tests ignored in the ordinary invocation |
| Windows native `--ignored --skip sleeper_fixture --skip launcher_fixture --test-threads=1` | All **three** real Core lifetime/packaging integrations passed |
| Installer/executable/diagnostics uploads | Passed; first green artifacts **11583313026 / 11582949065 / 11583417560** |

The installed owner-facing memory journey passed through real accessibility and
mouse/keyboard input; mutations used the UI, not direct SQLite writes:

1. Verify retrieval starts off; explicitly enable it and review/confirm
   “KAT should prefer local models when practical.”
2. Close/relaunch KAT, create a new conversation and ask the local/cloud preference
   question. Actual Ollama reflects the preference; the inspector shows record
   ID/revision **1** and owner-entered provenance.
3. Review/edit the wording to prefer cloud models. A new conversation still uses
   local inference, reflects the revised preference and records revision **2**
   only; both private revisions remain inspectable.
4. Open Forget, verify the transcript/backup notice and explicitly confirm.
   Current wording, revisions and FTS entries disappear. A new local conversation
   records **zero** memory usage and has no memory inspector.
5. Choose Remember on a user message, review/edit/confirm, verify selected-message
   session/message/role provenance and navigate back to its source conversation.

[Focused UI run **37854169898**](https://github.com/Google-Stein/KAT/actions/runs/37854169898)
also passed that entire real-Ollama sequence using the rebuilt executable from
run 37852681897 with the current acceptance helper. It did **not** install an NSIS
bundle and is diagnostic corroboration, not the full installed release gate.
[Core-only run **37850206839**](https://github.com/Google-Stein/KAT/actions/runs/37850206839)
passed actual time/repeated Notepad/Calculator selection and approval checks;
it does not establish UI or memory validation.

### Failures investigated before the green gate

- Runs **37848201789** and **37851161161** stopped after a saved memory edit.
  Geometry diagnosis in **37852115224** proved the enabled New conversation
  button had moved to **y=-477**: Memory lacked its own scrolling container, so
  focus/scroll moved the entire hidden-overflow app shell, including navigation.
  Adding the Memory pane's own overflow/padding fixed this product defect.
  Installed acceptance now asserts visible/enabled navigation after review;
  run **37852681897** proved revision-2 recall before reaching a later UI failure.
- **37849337086** produced no fresh time result during the real local tool loop.
  Its emitted tool payload was not retained, so an exact model-side cause is not
  claimed. Zero-memory turns now preserve the certified v0.2.1 prompt byte for
  byte; memory rules apply only when records are inserted. Safe audit diagnostics
  were added, and subsequent real time/application checks passed repeatedly.
- **37850174158** authenticated Core successfully, but a three-second independent
  HTTP probe canceled while WebView2 was creating the window. Probe execution
  now follows window creation and retries only classified transient network
  failures within the **unchanged 45-second** readiness deadline. The request
  timeout, required 401 and ownership checks remain unchanged; regression checks
  cover timeout, wrong HTTP status, wrapped errors and unexpected failures.
- **37851123579** could not scroll a provider control into view; **37852681897**
  stopped before Forget confirmation without sending a deletion request. CI's
  restored **1044×788** window exceeded its work area. The acceptance helper now
  focuses and normally maximizes the window (observed outer bounds
  **[-8,-8,1032,728]**) so real click targets stay onscreen. The complete installed
  sequence then passed; approval and deletion assertions were retained.
- Diagnostic run **37851721482** hit the helper's rectangle serialization error;
  explicit coordinates fixed it. **37853733975** stopped on an opaque KeyError
  before Calculator approval. Safe stack-location diagnostics were added;
  subsequent focused and full installed checks passed. Neither failed diagnostic
  is counted as validation. Superseded runs were canceled rather than published.

No startup timeout was increased and no debug port, renderer credential path,
remote endpoint, arbitrary executable or approval bypass was introduced.

Publication must use a successful **exact tagged-source** Core/Desktop/Windows
run, including the final documentation commit. The release notes link that final
run. The release workflow rejects mismatched/incomplete gates and uploads only
that run's installer plus SHA256SUMS; the first green run above is evidence for
this record, not permission to tag later unvalidated source.

### Remaining owner checks and limits

Live OpenAI account validity, quota and billing were not tested. OpenAI exclusion
uses the actual SDK with synthetic HTTP transport, not a live paid call. The
Windows Ollama acceptance uses Qwen3:1.7b on hosted CPU hardware; owner RTX 4090
performance, preferred larger models, paraphrase quality and sustained everyday
memory behavior require owner testing. The installer is unsigned and Windows
may show a publisher warning.

FTS5 is lexical, so synonyms/paraphrases may abstain. Pins do not force irrelevant
retrieval. Memory is ordinary local SQLite data, not encrypted by KAT; only normal
sensitivity is supported and recognizable credentials are rejected. Forget removes
active memory/revision/search wording, not original transcripts, old backups or
forensic WAL/filesystem copies. It cannot revoke an already running model's
context. Prior assistant replies remain ordinary transcript; an explicitly
selected cloud conversation may therefore contain the same words even though no
memory-record payload is injected. No automatic extraction or autonomy was added.

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

## 0.2.1 stale-tool-context hotfix — Windows gate passed

The owner reported a repeated 09:54 answer with no second `get_local_time` request.
The new deterministic HTTP-protocol regression reproduced that stale answer on
both OpenAI Agents SDK and Ollama before the fix (two expected failures). Promoting
persisted tool messages into user text exposed old outcomes without their matching
assistant tool calls. The shared history builder now omits those records from
future inference, along with the original assistant content from historical tool turns; active
loop results, SQLite, approval cards, transcript and audit
are preserved. Shared instructions require new time/action calls on new requests.

The owner checked the failed Calculator attempt's Activity/approvals and reported
**no Calculator tool request**. That attempt was a model-selection failure, not an
observed Windows launcher failure. Tests now cover Calculator after earlier time
and Notepad activity and repeated Calculator requests. The production allowlist,
fixed native `.exe` launch, shell restrictions and approvals are unchanged.

Cloud checks passed: **148 Python tests**, including both actual provider wire
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

[First hotfix run 37806956575](https://github.com/Google-Stein/KAT/actions/runs/37806956575)
passed Core/desktop, Python 3.12.10 packaging, and real packaged window/authenticated
owned-Core/normal-close/forced-termination checks. Installation stopped before
inference because restoring the Cargo output cache retained an older 0.2.0 NSIS
installer beside the newly built 0.2.1 installer. The installer test correctly
rejected ambiguous artifacts. The build now removes only previously generated
`KAT_*-setup.exe` files in its repository build-output directory before bundling.
No installation or user-data directory is cleared. During review, the extended
UI harness also needed to wait for an approval card instead of an enabled composer
on application requests: pending approval intentionally disables that composer.
These corrections require another full Windows run; no timeout was increased.

[Focused real-Ollama run 37807882322](https://github.com/Google-Stein/KAT/actions/runs/37807882322)
exposed a second stale-evidence path: removing raw tool records alone still left
the previous assistant timestamp in model context. The repeated time request did
not generate a fresh result. New deterministic regressions reproduced this for
both provider wire protocols and for tool results before/after the assistant reply
(four expected failures). The shared builder now also omits assistant replies from
historical tool turns. User messages and ordinary conversation replies remain;
all omitted inference data stays in the full stored transcript and audit. A focused
Core-only real-backend diagnostic is distinct from the mandatory full installed
UI gate; it never substitutes for Windows release validation.

[Run 37808750400](https://github.com/Google-Stein/KAT/actions/runs/37808750400)
passed actual Core/local repeated time, repeated Notepad and repeated Calculator
selection/approval/native process execution. Its installed production UI passed
credentials, two identical time requests with newer results, and two distinct
Notepad approvals/windows. It stopped on an ambiguous control at Calculator
selection; the harness now enumerates approval buttons and reports validated
pending application IDs if the count is unexpected. Dropping tool-turn assistant
messages entirely leaves old user requests apparently unanswered. Their original
content is now replaced with a constant, result-free historical marker, preserving
turn structure without exposing stale timestamps, status or launch results.
[Core-only run 37809113626](https://github.com/Google-Stein/KAT/actions/runs/37809113626)
passed the real local sequence; earlier focused run 37808749889 did not produce
a fresh time result. These are recorded distinctly from the full release gate.

### Full current-source Windows result

[Run **37810325045**](https://github.com/Google-Stein/KAT/actions/runs/37810325045)
finished successfully at **2026-10-08 16:47:27 UTC (10:47:27 MDT)**, source
**`7ca54193dda9b3a81e085bec2ca7531fc631a691`**. **Core, desktop and Windows
all passed.** The final documentation commit must pass those gates again on its
exact source before tagging/publishing; release notes identify that final run.

| Actual command/check | Result |
| --- | --- |
| `uv run --directory core pytest tests ../tests/integration -q` | **148 passed** in cloud and Linux CI; OpenAI SDK/Ollama deterministic wire regressions passed |
| Core and scripts Ruff / format / strict mypy | Passed; all 16 source modules typed |
| `python scripts/version.py --check` | Passed; root/Python/npm/Cargo/Tauri all **0.2.1** |
| Standalone and rebuilt Linux packaged `scripts/smoke-core.py` | Actual authentication, keyless error, persistence, restart and shutdown passed |
| Frontend tests / ESLint / Prettier / TypeScript / Vite | **26 tests passed**, all checks/build passed |
| Linux native tests / fmt / full Clippy | **20 passed, 4 deliberate ignores**; formatting and warnings-denied Clippy passed |
| Linux `cargo test ... -- --ignored --skip sleeper_fixture --test-threads=1` | All **3 explicit native service integrations passed** against rebuilt current-source Core |
| Windows-target all-targets Clippy in cloud | Passed with warnings denied; actual Windows execution separately below |
| `scripts/build-windows.ps1 -PythonExecutable <setup-python executable>` | Python **3.12.10 x64**, current-source desktop/PyInstaller/NSIS passed; two cached old installers cleared before bundling |
| `scripts/smoke-windows.ps1` | Window, exact owned packaged Core/listener, authenticated readiness, 401 without bearer, normal/forced close and port release passed |
| `scripts/smoke-installed-windows.ps1 -LocalInference` | Current-user install into path with spaces, installed lifecycle, persistence, real UI/Ollama and uninstall passed |
| `scripts/smoke-local.py` with actual Ollama **0.40.1 / Qwen3:1.7b CPU** | Greeting, two identical time requests with newer results, two Notepad requests and two Calculator requests each with fresh approval/execution passed; OpenAI unavailable |
| Installed production WebView `scripts/smoke-installed-ui.py` | Native credential cancel/save/replace/restart/remove; real local greeting; two fresh time results; two distinct Notepad approval/window pairs; Calculator approval and actual window all passed |
| Installed close/relaunch/uninstall | Both Notepads and Calculator survived normal KAT close; all five historical tool records retained; provider/model/chat/audit survived relaunch; uninstall retained integrity-checked SQLite |
| Windows Python unit/integration tests | **147 passed, 1 POSIX execute-bit skip** |
| Windows packaged `scripts/smoke-core.py --executable .../kat-core.exe` | Actual process authentication/persistence/restart/shutdown passed |
| Windows native tests | **21 passed, 5 deliberate ignores**, plus all **3 explicit Core integrations passed** |
| `tests/integration/test_windows_smoke_diagnostics.ps1` | All **13 diagnostics checks passed**; build-script syntax also passed in cloud |
| Installer / executable / diagnostic uploads | Passed: **11564673804 / 11564808556 / 11565048225** |

The owner's Calculator audit contained no request, establishing a selection failure
for that attempt. The unchanged fixed `System32/calc.exe` launcher now has separate
actual Windows window evidence after a genuine local-model request and UI approval.
Neither allowlisting nor approval was relaxed. Historical tool records and their
original assistant replies remain stored and displayed; inference receives no old
result through those records or reply summaries. Active tool-loop results remain
available immediately. Tests cover automatic time permission decisions and new
manual application approvals for both providers. No schema/memory changes occurred.

Backend/runtime/weights were explicitly downloaded for disposable CI with upstream
SHA-256 checks, not bundled with KAT. This certifies the tested CPU model and
sequences; owner RTX 4090/Qwen3:8b and live OpenAI account tests remain separate.
