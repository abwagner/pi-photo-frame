# Multi-display unique-content design

## Decision summary

Use a small SQLite database in WAL mode as a centralized assignment authority.
Every enrolled display receives its own identity and reports a capability profile.
The server atomically leases slides—and every photo contained by those slides—to
displays. A client must blank before its lease expires if it cannot renew.

That last rule is necessary for a real uniqueness guarantee. If an offline display
continues showing a photo after the server's lease expires, the server cannot both
reassign that photo and guarantee it is not still visible. Availability and strict
uniqueness cannot both be preserved across a network partition. OpenFotoFrame should
offer two explicit modes:

- `strict`: blank before lease expiry; guarantees no photo is knowingly displayed by
  two compliant clients at once.
- `available`: continue the last slide while offline; visually preferable, but
  uniqueness becomes best-effort until the display reconnects.

The default for a feature advertised as “guaranteed unique” must be `strict`.

## Definition of uniqueness

The reservation unit should be the underlying photo asset, not merely a composed
slide. If one display receives a three-photo group, all three photo IDs are reserved;
no other display may receive any single or group slide containing those photos.

The guarantee applies to enrolled, policy-compliant displays with unexpired leases.
It requires at least as many eligible, mutually disjoint photo sets as active displays.
When there is insufficient content, the allocator returns `no_unique_content`; strict
clients show a configurable neutral/clock screen rather than reuse an assigned photo.

## Display identity and capabilities

Display enrollment should create a server-side record and put only an opaque display
ID plus session generation in the signed browser session:

```text
displays
  id UUID primary key
  name text
  enabled boolean
  session_generation integer
  last_seen_at timestamp
  capability_json text
  created_at timestamp
```

Reported capabilities:

- CSS viewport width and height;
- device-pixel ratio;
- orientation;
- supported image formats;
- preferred maximum decoded dimensions;
- client version;
- strict/available offline policy.

The server must validate and bound these values; they are optimization inputs, not
authorization claims. Administrators can name, disable, and re-enroll each display.

## Atomic lease allocator

SQLite is a better fit than the current JSON files for concurrent assignment state
while preserving the project's lightweight, self-hosted character. Use WAL mode,
foreign keys, a short busy timeout, and `BEGIN IMMEDIATE` for allocation.

```text
assignments
  id UUID primary key
  display_id UUID unique references displays(id)
  slide_id text
  lease_token_hash text
  not_before timestamp
  lease_expires_at timestamp
  sequence integer

asset_reservations
  asset_id text primary key
  assignment_id UUID references assignments(id) on delete cascade
  lease_expires_at timestamp
```

Allocation transaction:

1. Begin an immediate transaction.
2. Delete expired assignments/reservations.
3. Renew the calling display's current assignment when appropriate, or release it
   after the client acknowledges transition completion.
4. Build eligible slides from enabled content and display policy/filter rules.
5. Exclude any slide containing an asset present in `asset_reservations`.
6. Choose fairly from the remaining candidates.
7. Insert one assignment plus reservations for every underlying asset.
8. Commit and return a random lease token once; store only its hash.

`asset_id` being a primary key is the database-enforced uniqueness boundary. A single
transaction reserves every member of a group, so concurrent requests cannot split or
duplicate group content.

SQLite serializes only the very short allocation transaction. Photo delivery and
rendering remain outside it, so dozens of displays are practical on a Raspberry Pi.

## Client protocol

Suggested endpoints:

```text
POST /api/displays/capabilities
POST /api/displays/assignment/next
POST /api/displays/assignment/heartbeat
POST /api/displays/assignment/release
GET  /api/displays/assignment/<id>/image
```

All are browser-session authenticated and mutations remain CSRF-protected. `next`
accepts the prior assignment ID and completion acknowledgement. Responses include:

```json
{
  "assignment_id": "uuid",
  "lease_token": "shown-once-random-token",
  "lease_seconds": 90,
  "renew_after_seconds": 30,
  "not_before": "server timestamp",
  "slide": {},
  "variant_url": "/api/displays/assignment/.../image"
}
```

The client uses a monotonic countdown derived from `lease_seconds`, not its wall
clock. In strict mode it begins transitioning to the neutral screen with a safety
margin before expiry. Heartbeats extend the database lease only when the hashed lease
token, display session, and assignment all match.

Lease-protected image URLs contain only assignment IDs; authorization comes from the
display cookie and lease token in an HTTP header, never a query string.

## Selection and fairness

The current daily shared shuffle cannot produce different displays. Replace it with
a server-side score among currently eligible slides:

1. least recently shown globally;
2. least shown during the current scheduling window;
3. avoid the requesting display's recent history;
4. deterministic random tie-breaker.

Persist a bounded history. Do not hold one long playlist per display: allocating one
lease at a time reacts correctly when displays join, disconnect, content changes, or
an administrator disables an image.

Optional per-display playlists/tags are filters applied before the uniqueness check.
If two displays have disjoint playlists, allocation is trivial; overlapping playlists
are resolved by the same reservation transaction.

## Rendering strategy

Pre-rendering is not required for uniqueness. Keep originals canonical and begin by
returning assignment-specific source metadata to the existing CSS renderer. That is
the smallest first release and naturally adapts to arbitrary viewport sizes.

Pre-rendered variants are valuable later for low-powered clients, deterministic group
composition, and reduced browser memory. Avoid one render per exact screen size; that
creates an unbounded cache. Use a render-profile key:

```text
content revision
+ slide/group metadata revision
+ aspect bucket
+ orientation
+ resolution tier
+ fit/crop/mat/effect settings
+ output format/encoder version
```

Recommended aspect buckets:

- landscape: 16:9, 16:10, 4:3, and ultrawide;
- portrait: 9:16 and 3:4;
- square;
- custom fallback using the nearest bucket with CSS letterboxing.

Recommended resolution tiers are based on the physical pixel long edge (for example
1280, 1920, and 3840), capped by the original. A 1920×1080 and 3840×2160 display can
share the 16:9 composition while receiving different resolution tiers. Group layouts
should render by aspect bucket because composition changes materially with aspect;
single-photo `contain` slides often need only a resolution variant.

Store variants content-addressed under the data volume. Generate on demand into a
temporary file, atomically rename, and reuse. Metadata/settings changes create a new
key, so invalidation is implicit; an LRU/size cap removes unreachable old variants.
Never block the lease transaction on rendering: allocate first, render/cache outside
the transaction, and let the client retain its prior lease or neutral screen until the
variant is ready.

## Rollout plan

1. **Identity:** add per-display records, names, capabilities, and administrator
   enable/revoke controls while retaining today's shared slideshow behavior.
2. **Allocator:** move assignment state to SQLite, add asset-level leases, strict
   blank-on-expiry behavior, and concurrency/partition tests.
3. **Scheduling:** add global fairness history and optional per-display tag/playlists.
4. **Variants:** introduce aspect buckets and on-demand content-addressed rendering;
   measure storage/CPU before adding eager background pre-rendering.
5. **Operations:** add assignment observability, stale-display cleanup, backup/migrate
   the SQLite file, and document uniqueness-versus-availability policy.

## Required tests

- concurrent `next` requests never reserve the same underlying asset;
- group reservations exclude every member photo;
- insufficient content produces `no_unique_content` rather than reuse;
- strict clients blank before lease expiry and after loss of heartbeat;
- expired leases are reclaimed atomically;
- stale/incorrect lease tokens cannot renew, release, or fetch images;
- disabled displays and rotated sessions lose assignments;
- aspect/profile keys are deterministic and invalidate on content/settings revision;
- renderer failures do not leak reservations indefinitely;
- restart recovery preserves unexpired leases and prunes expired ones.
