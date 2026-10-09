# Bounded capabilities (0.4)

The owner approves this milestone's weather lookup, local system status and
read-only local folders. Tools propose strict structured intent; trusted code
executes it. No shell, arbitrary URL, browser automation or file modification is
exposed. Existing conversation, memory and provider boundaries stay intact.

Weather uses Open-Meteo's fixed HTTPS geocoding and forecast endpoints, separately
from the AI provider. The owner enters a place, resolves it explicitly, and confirms
one returned location. No OS geolocation or tracking is used. The place/coordinates
leave the device for Open-Meteo, including when AI inference is local. This first
adapter is for personal noncommercial use under upstream terms; availability is
external. Requests reject redirects, ignore proxy environment, use fixed hosts,
bounded streamed responses (128 KiB), eight-second timeout, no retries and bounded
parsed fields. Every weather request fetches fresh data; no historical result cache.

System status uses psutil and Windows APIs, with no shell or command-line
inspection. It returns fresh CPU/RAM/disk/uptime metrics, OS identification and
optional GPU information. GPU unavailable is explicit and nonfatal. At most eight
local fixed disks are returned; no network mounts, environment or process data.

Only Settings can register a root, through a native folder picker on Windows or
explicit authenticated owner configuration in browser development. Registration
is absent from the model tool registry. Root IDs and labels are advertised; raw
absolute paths stay in owner configuration. Network/UNC/device namespaces, drive
roots and reparse/symlink paths are rejected. Removal revokes future operations,
including pending approvals. Each operation revalidates the root and arguments.

File tools take root ID and bounded relative paths only. Parent/absolute/drive/ADS/
device syntax, trailing-dot/space aliases and symlink/reparse escapes are rejected.
POSIX traversal uses anchored directory descriptors and O_NOFOLLOW. Windows opens
and pins each directory without delete-sharing, rejects reparse points and verifies
handle-resolved containment before reading, avoiding a check-then-open escape.

Listing is nonrecursive: at most 100 returned entries and 1,000 inspected entries.
Filename search inspects at most 1,000 entries, depth four, 50 matches and two
seconds; it never reads file bodies. Text read always requires individual approval,
uses an allowlisted text extension, accepts UTF-8 (optional BOM), rejects NUL/binary
and oversized files (64 KiB), and returns at most 12,000 characters with explicit
truncation. No writes, delete, rename, content search or durable approval grants.
Blocking OS operations on a failed local disk remain subject to the OS; network
roots are prohibited. Work runs outside the API event loop.

Tool results enter the active loop when immediately authorized. Content reads
execute only after approval, then return in the approval card/transcript; they do
not automatically start a new model request. Both providers use the same dispatcher.
Operational audit records file metadata/byte counts only, not bodies. The normal
local SQLite transcript and approval result do retain returned text; older tool
messages/replies remain excluded from future inference. No automatic memory is
created. Explicit Remember on ordinary user/assistant text keeps its existing rules.
