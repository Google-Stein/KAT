# Bounded capabilities (0.4)

The owner approves this milestone's weather lookup, local system status and
read-only local folders. Tools propose strict structured intent; trusted code
executes it. No shell, arbitrary URL, browser automation or file modification is
exposed. Existing conversation, memory and provider boundaries stay intact.

Tool-capable model metadata does not guarantee correct arguments. Windows
acceptance uses Qwen2.5:7b CPU; Qwen3:8b remains the recommended starting point for
the owner's RTX 4090. Small models can invent arguments; KAT rejects these calls,
never strips unknown fields, fabricates metrics or silently selects another model.
Existing saved model choices are preserved. See VALIDATION.md for actual gates.

Weather uses Open-Meteo's fixed HTTPS geocoding and forecast endpoints, separately
from the AI provider. The owner enters a place, resolves it explicitly, and confirms
one returned location. No OS geolocation or tracking is used. The place/coordinates
leave the device for Open-Meteo, including when AI inference is local. This first
adapter is for personal noncommercial use under upstream terms; availability is
external. Requests reject redirects, ignore proxy environment, use fixed hosts,
bounded uncompressed streamed responses (128 KiB), an eight-second request budget,
3.5-second transport attempts and at most one retry for transport failure while
budget remains. Redirects, HTTP failures and malformed data are not retried.
Parsed fields stay bounded. Each weather request fetches fresh data; no history cache.

System status uses psutil and Windows APIs, with no shell or command-line
inspection. It returns fresh CPU/RAM/disk/uptime metrics, OS identification and
optional GPU information. GPU unavailable is explicit and nonfatal. At most eight
local fixed disks are returned; no network mounts, environment or process data.
The strict `metric` selector permits only `ram`, `cpu`, `disks`, `gpu`, `os` or
`all` (default overview). Each call collects fresh state, returning the selected
category plus collection/OS/availability metadata. It accepts no command or path.

Only Settings can register a root, through a native folder picker on Windows or
explicit authenticated owner configuration in browser development. Registration
is absent from the model tool registry. Root IDs and labels are advertised; raw
absolute paths stay in owner configuration. Network/UNC/device namespaces, drive
roots and reparse/symlink paths are rejected. Removal revokes future operations,
including pending approvals. Each operation revalidates the root and arguments.
File tool definitions are offered to both models only when at least one root is
registered; trusted implementations remain strict regardless of visibility.
Friendly labels are not path prefixes. Before a content approval, KAT checks only
target metadata inside pinned parents, rejecting missing/unsupported/oversized
targets without reading their body. This preflight has a 12-second caller deadline;
the target and bounds are revalidated again when the owner approves.
At most 12 roots are registered. Owner labels are limited to 80 characters and
root paths to 240; model relative paths are at most 240 and filename queries 80.
Weather place lookup accepts 100 characters and returns at most five choices.

File tools take root ID and bounded relative paths only. Parent/absolute/drive/ADS/
device syntax, trailing-dot/space aliases and symlink/reparse escapes are rejected.
POSIX traversal uses anchored directory descriptors and O_NOFOLLOW. Windows opens
and pins each directory without write/delete-sharing, rejects reparse points and verifies
handle-resolved containment before reading, avoiding a check-then-open escape.

Listing is nonrecursive: at most 100 returned entries and 1,000 inspected entries.
Entries include exact root-relative paths; names outside the supported path
syntax/length are omitted rather than truncated into different file addresses.
On a missing file, the model may fetch a fresh listing and propose one corrected
read; permission and path validation apply again. No automatic path rewrite occurs.
Filename search inspects at most 1,000 entries, depth four, 50 matches and two
seconds; it never reads file bodies. Text read always requires individual approval,
uses an allowlisted text extension, accepts UTF-8 (optional BOM), rejects NUL/binary
and oversized files (64 KiB), and returns at most 12,000 characters with explicit
truncation. No writes, delete, rename, content search or durable approval grants.
Blocking OS operations on a failed local disk remain subject to the OS; network
roots are prohibited. Work runs outside the API event loop.

Tool results enter the active loop when immediately authorized. Content reads
execute only after approval, then return in the approval card/transcript. In 0.4.1
an unchanged originating Ollama task may resume with these results as untrusted
tool data. Cloud-origin reads do not automatically send contents to any model.
Both providers use the same dispatcher.
Operational audit records file metadata/byte counts only, not bodies. The normal
local SQLite transcript and approval result do retain returned text; older tool
messages/replies remain excluded from future inference. No automatic memory is
created. Explicit Remember on ordinary user/assistant text keeps its existing rules.

## Approved task continuation limits (0.4.1)

One owner request can create at most six individual approvals and three automatic
continuations. All initial/resumed inference shares a 120-second active budget;
time spent waiting for owner approval is excluded. Local HTTP requests keep their
90-second bound; each tool keeps its 12-second deadline. The 64-KiB file and 12,000
returned-character limits are unchanged. Aggregate serialized approved results
are capped at 28,000 characters; oversized combinations remain visible locally
but do not continue automatically. Model/token limitations may fail sooner.

Sequential reads retain earlier approved results only inside that active task.
Simultaneous approvals wait until all decisions resolve, then one model call
continues deterministically under the session lock. Denial/failure suppresses the
chain. Each additional read still requires a new approval. A changed provider,
model, endpoint, route revision, project scope or newer owner message suppresses
automatic reasoning but permits exact explicitly approved execution when safe.
Restart never retries claimed reads or interrupted reasoning. A completed local
result remains available; its model answer is not falsely marked completed.
