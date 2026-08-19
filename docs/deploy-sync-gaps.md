# Deploy & asset-sync gaps

Briefing for a work session in this project. Written 2026-08-19, after tracking down
seven broken favicons on 11tybundle.dev. **The favicons are already fixed and deployed
— nothing is broken right now.** What remains is the three underlying gaps that let
them break silently, all of which live in this repo.

**All three gaps are resolved** (see below).

## What happened

`https://11tybundle.dev/authors/cassie/` was rendering a broken favicon image. The file
was correct in both `11tybundledb/favicons/` and `11tybundle.dev/_site/img/favicons/`
(byte-identical, valid PNG), and the built HTML pointed at the right name — it simply
had never been uploaded to Cloudflare.

Sweeping all 1,659 files in `_site/img/favicons/` against production found exactly one
missing. Reconciling every `favicon` reference in `bundledb.json` + `showcase-data.json`
against both directories found six more that would 404 as soon as anything linked them:

```
referenced favicon filenames                    : 1630
referenced but missing from 11tybundledb/       : 2   (no source file at all)
referenced but missing from _site/img/favicons/ : 7
```

Resolved by copying five, refetching two via `services/favicon.py` (quinndaedal.com,
web-standards.ru), and correcting one `.ico` -> `.png` reference in `bundledb.json`
where the refetch changed the extension. Committed to `11tybundledb` as `48e029a`.
Post-deploy sweep: all 434 favicons on `/authors/` return 200, previously 2 broken.

## Gap 1 — asset sync only walks the current issue — RESOLVED

`services/prebuild_sync.py:192` — `check_and_copy_assets()`

It iterates `load_recent_issue_entries()`, so only entries in the current issue are
checked. Any favicon, screenshot, or og-image belonging to an older entry that goes
missing from `_site` is never noticed and never re-copied. That is the root cause of all
seven; several had been dead for months.

The per-file copy is also existence-gated:

```python
if not os.path.exists(dest):
    if os.path.exists(src):
        shutil.copy2(src, dest)
```

So an asset that is present but *stale* is never refreshed either.

**Watch out**: `shutil.copy2` preserves mtime, so a file's timestamp in `_site` reflects
when the asset was *created*, not when it was copied. That is what made the original
diagnosis confusing — do not use `_site` mtimes to reason about deploy order.

### What was built

`check_and_copy_assets()` now reconciles every asset reference in the full DB. Documented
in `docs/workflows-reference.md` under "Pre-Build Sync"; 13 new tests in
`tests/test_prebuild_sync.py`. Four things the implementation turned up that the briefing
did not anticipate:

- **673 bundledb entries have no `Issue` field at all** (657 blog posts, 14 starters), so
  an issue-based walk could never have reached them regardless of window size.
- **showcase-data.json is the larger set** — 1,607 entries against 848 `site` entries in
  bundledb, with 10 db sites absent from showcase. `collect_asset_refs()` walks both files
  independently rather than merging one into the other. Starters carry their own
  `screenshotpath` on the bundledb entry (39/39).
- **og-images had no repair path at all.** The 2026-05-06 og-image design deferred
  prebuild_sync on the grounds that capture/backfill write both destinations directly —
  true at fetch time, but nothing could fix a later deletion. They are covered now.
- **Symmetric mtime comparison was the wrong staleness rule.** It flagged 1,371 files, all
  screenshots, all byte-identical: `capture-screenshot.js` writes `content/screenshots` and
  `11tybundledb` in the same run rather than copying, so their mtimes never matched.
  `_copy_state()` compares mtime one-directionally — only a source newer than its
  destination is stale. That cut 1,371 candidates to 3, one of which
  (`tghb-studio-large.jpg`) was a real stale copy with matching size and different bytes
  that a size-only rule would have missed.

Missing source files block the build only for the recent-issue window; older ones surface
as non-blocking `warnings`. Current state: 4,845 refs, 0 missing, 0 warnings, 3 pending
refreshes, ~100ms for the whole sweep.

## Gap 2 — deploy does not push already-committed work — RESOLVED

`app.py:1643` — `_commit_and_push_bundledb()`

```python
if not status.stdout.strip():
    return {"success": True, "message": "No DB changes to commit."}
```

That early return fires **before** the push. The function only handles uncommitted
working-tree changes; if the tree is clean it reports success and pushes nothing. A
local commit that has not reached origin is invisible to it.

Observed directly: a commit was made by hand, a deploy ran, the deploy reported success,
and the commit stayed local. `docs/workflows-reference.md:25` encodes the same
assumption — "Nothing to commit is treated as success".

### What was built

`_commit_and_push_bundledb()` now acts on two independent signals — a dirty working tree
and a branch ahead of its upstream (`_bundledb_ahead_count()`, `git rev-list --count
@{u}..HEAD`). It commits when the tree is dirty and pushes when either is true. Only a
clean tree that is also in sync returns early, now saying "No DB changes to commit or
push."; a clean-but-ahead branch reports "Pushed N previously committed change(s)." A
branch with no upstream reports 0 ahead and falls back to the old behavior rather than
erroring.

The function had no tests at all. It has seven now, in `tests/test_editor_routes.py`,
stubbing `subprocess.run` by git subcommand. Five of them passed against the old code —
the two that did not are this gap: a clean-but-ahead tree was never pushed, and a push
failure in that state was never reported.

`docs/workflows-reference.md` said "Nothing to commit is treated as success", which
encoded the bug; it now describes the two-signal rule.

Not addressed here: Gap 3. This function still pushes without rebasing.

## Gap 3 — deploy pushes without rebasing — RESOLVED

Same function. It runs `git add -A` -> `commit` -> `push`, with no pull. The sibling
function `sync_bundledb_repo()` (`services/prebuild_sync.py:35`), reached only via
`/editor/prebuild-sync`, does `add` -> `commit` -> `pull --rebase origin main` -> `push`
and aborts the rebase on conflict.

So the same repo is managed by two functions with different safety properties and
different commit messages:

| | `_commit_and_push_bundledb()` | `sync_bundledb_repo()` |
|---|---|---|
| Called by | `/editor/deploy`, `/editor/verify-site` | `/editor/prebuild-sync` |
| Message | `"New entries saved"` | `"Added new entries"` |
| Steps | status -> **early return if clean** -> add -> commit -> push | add -> commit -> **pull --rebase** -> push |

If origin ever moves ahead, deploy's push just fails and surfaces as `git push failed:`
in `git_result`. The `11tybundledb` history is currently all "Added new entries", which
suggests commits have been coming from prebuild-sync rather than deploy.

### What was built

Consolidated. `sync_bundledb_repo(commit_message=...)` in `services/prebuild_sync.py` is
now the only function that touches this repo, and `_commit_and_push_bundledb()` is gone
from `app.py`. `/editor/deploy` and `/editor/verify-site` call it with their own commit
messages — "New entries saved on deploy" and "New entries saved after local build" — so
the log stays a signal for which flow produced a commit, which is what revealed Gap 2.

Fixing Gap 3 by construction rather than by adding `pull --rebase` to the second function:
after the Gap 2 fix the two were doing nearly the same job by different code, which was the
real problem the table below describes.

`_ahead_count()` moved into `prebuild_sync.py` alongside it. `sync_bundledb_repo()` already
pushed unconditionally, so it never had Gap 2; the count now appears in its message when
there was nothing new to commit.

The six existing tests used ordered `side_effect` lists, which break whenever a step is
added to the sequence. They were rewritten onto a stub that dispatches on the git
subcommand — eleven tests now, plus five route-level tests in `tests/test_editor_routes.py`
asserting each route calls the shared helper with its own message and that a git failure
never fails a successful deploy.

The table below records what the two functions looked like before consolidation.

## Verification recipe

Reconcile every asset reference against both the source repo and the build output:

```bash
cd /Users/Bob/Dropbox/Docs/Sites/11tybundle
python3 - <<'PY'
import json, os
DB="11tybundledb"
for key, label, srcdir, dstdir in [
    ("favicon",        "favicon",     f"{DB}/favicons",    "11tybundle.dev/_site/img/favicons"),
    ("screenshotpath", "screenshots", f"{DB}/screenshots", "11tybundle.dev/content/screenshots"),
    ("ogImagePath",    "og-images",   f"{DB}/og-images",   "11tybundle.dev/content/og-images"),
]:
    refs = set()
    for f in (f"{DB}/bundledb.json", f"{DB}/showcase-data.json"):
        for e in json.load(open(f)):
            v = e.get(key) or ""
            if v and not v.startswith("#"):
                refs.add(os.path.basename(v))
    src = set(os.listdir(srcdir)) if os.path.isdir(srcdir) else set()
    dst = set(os.listdir(dstdir)) if os.path.isdir(dstdir) else set()
    print(f"{label:12} refs={len(refs):5} no-source={len(refs-src):3} not-in-site={len(refs-dst):3}")
    for n in sorted(refs-src)[:6]: print(f"     NO SOURCE  : {n}")
    for n in sorted(refs-dst)[:6]: print(f"     NOT IN SITE: {n}")
PY
```

Check what is actually live (~90s, safe to run against production):

```bash
cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/_site/img/favicons
ls | xargs -P 24 -I{} sh -c \
  'c=$(curl -s -o /dev/null -w "%{http_code}" "https://11tybundle.dev/img/favicons/{}"); [ "$c" != "200" ] && echo "$c {}"'
```

A favicon present in `_site` but 404 on production means it was copied in after the last
deploy — build and deploy again. Newly added entries will show here as false positives
until their first deploy: favicons reach `_site` immediately (`_copy_to_site()` runs at
fetch time) while screenshots and og-images wait for a build to passthrough-copy them.

## Constraints for this work

- Activate the venv for every Python command: `source .venv/bin/activate && pytest`.
- `tests/test_prebuild_sync.py` already covers `sync_bundledb_repo()` and
  `check_and_copy_assets()` — read it before changing either. Full suite is 310 tests.
- The app runs on port 5555 with `debug=True` (`app.py:2095`), so editing `app.py`
  auto-reloads the running server. Two PIDs for it is the werkzeug reloader, not a
  duplicate. `services/prebuild_sync.py` is imported lazily inside the route, so changes
  there take effect on the next request.
- Per CLAUDE.md: when committing to `main`, push immediately after.
- `services/verify_site.py` still checks `_site` HTML for the latest issue only. Gap 1 was
  fixed in `prebuild_sync` rather than here, on the grounds that prebuild runs before the
  build and can actually repair, while verify runs after and can only report.

## Also noticed, not investigated

- **`docs/commit-push-on-deploy.md` is stale.** It describes deploy as *not* committing
  or pushing and asks for the feature. That was implemented, and the function it describes
  no longer exists — deploy now calls `sync_bundledb_repo()`. Fold it into this doc or
  delete it. Still not done.
- **SVG favicons are fragile as `<img src>`.** cassie.ink's is `fill="currentColor"`
  (renders flat black, no color context); `f26rm-ryancordell-org-favicon.svg` draws an
  emoji as `<text>` with `font-family="AppleColorEmoji"`, so it only renders in color on
  Apple devices. Neither is broken today. Rasterizing SVG favicons to 64x64 PNG on fetch,
  as `_save_favicon()` already does for other formats, would make them render
  consistently — but that is a product decision, not a bug fix.
