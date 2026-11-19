# Script Revision API

## Status

Implemented in code and tested against an isolated database. **Not live**:
the running backend has not been restarted, so migration `4` (`script_revisions`)
has not been applied to the production database. V3 has **not** been installed
into episode `073b5d75f0c4`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/episodes/{episode_id}/script-revisions/state` | Current script hash, current/latest revision, approval state |
| `POST` | `/api/episodes/{episode_id}/script-revisions` | Create a validated revision and make it current |
| `GET` | `/api/episodes/{episode_id}/script-revisions?limit=50&include_script=false` | Revision history |
| `GET` | `/api/episodes/{episode_id}/script-revisions/{revision_id}` | One revision with full script |

## Create payload

```json
{
  "script": { "story": { "scenes": ["..."] } },
  "base_revision_id": "optional previous revision id",
  "expected_current_sha256": "required when replacing an existing script",
  "notes": "why this revision exists"
}
```

Accepted script shapes:

- `{"story": {"scenes": [...]}}` — the installed V1/V3 shape;
- `{"scenes": [...]}` — the generator's top-level shape.

The stored shape is preserved, and the revision records
`script_format: "story_scenes"` or `"scenes"`.

## Validation

- script must be a JSON object;
- one of the two supported scene shapes;
- 1–100 scenes;
- each scene needs a non-empty title, a characters list and a dialogue list;
- each dialogue line needs a non-empty speaker and text;
- optional summary/action/camera/background must be strings;
- optional duration_seconds must be a non-negative number;
- max 250 dialogue lines per scene; max text/notes lengths enforced.

Invalid payloads return HTTP 400 and write nothing.

## Safeguards

- `expected_current_sha256` is **required** when the episode already has a
  script. A mismatch returns HTTP 409 and writes nothing.
- `base_revision_id`, when supplied, must be the latest revision for that
  episode; otherwise HTTP 409.
- Creating a revision sets:
  - `production.script_approved = false`
  - `production.script_approval_reset_at`
  - `production.script_revision_id`, `script_revision_number`, `script_sha256`,
    `script_format`
  - `production.storyboard_stale = true`
  - `episodes.approved_at = NULL`, `approved_by = NULL`
- Every revision is written to `script_revisions` with revision number, hash,
  format, scene/line counts, base revision, actor, notes and timestamp.
- An `audit_logs` entry is written for each revision.
- No approval is granted by this API.

## Revision history

`GET .../script-revisions` returns newest first. Each item includes
`revision_id`, `revision_number`, `sha256`, `script_format`, `scene_count`,
`dialogue_lines`, `base_revision_id`, `actor`, `notes`, `created_at`,
`is_current`. Add `include_script=true` for the full document.

## Tests

```powershell
cd D:\bro\CartoonStudio\backend
.\.venv\Scripts\python.exe -m pytest tests\test_script_revisions.py -q
```

Coverage:

- valid V3 revision, counts and hash;
- invalid payload rejected with no writes;
- revision history and full retrieval;
- stale hash conflict;
- approval reset on script change;
- supported API route valid and invalid requests.

Result: **9 passed** in the focused file; **104 passed** for the full suite.

## Migration

`backend/app/db_migrations.py` adds migration 4:

```sql
CREATE TABLE script_revisions (...);
CREATE INDEX idx_script_revisions_episode ...;
```

The live database still reports migrations 1–3. Applying migration 4 requires a
controlled backend restart (not performed).

## Controlled installation of V3 (do not run yet)

1. Schedule a controlled backend restart so `init_db()` applies migration 4.
2. `GET /api/episodes/073b5d75f0c4/script-revisions/state` and capture
   `current_sha256` (V1).
3. `POST /api/episodes/073b5d75f0c4/script-revisions` with:
   ```json
   {
     "script": <S01E01_SCRIPT_V3.json>,
     "expected_current_sha256": "<current_sha256 from step 2>",
     "notes": "Install validated V3 naturalness revision"
   }
   ```
4. Verify the response `revision_number`, `sha256`, `script_approved: false`.
5. `GET .../script-revisions?include_script=true` and confirm V3 is current.
6. Confirm `episodes.approved_at` is NULL and `storyboard_stale` is true.
7. Do **not** approve, do not regenerate scenes/storyboard, and do not start
   keyframes until the script is reviewed and the character gate passes.

## Known limitation

The new API preserves the `story.scenes` shape used by V1/V3.
`storyboard_service.create_storyboard` currently reads top-level `script.scenes`
or `production.script.scenes`, so scene regeneration from V3 still needs a
shape-normalisation fix or a storyboard adapter. This is separate from the
revision API and is not changed here.
