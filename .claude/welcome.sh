#!/usr/bin/env bash
# Prints the social-posting usage summary at session start (SessionStart hook).
# Output is JSON with a systemMessage field, displayed to the user in the UI.

read -r -d '' MESSAGE <<'EOF'
social-posting — Socially Bundled, the local editorial tool for 11tybundle.dev

WHAT IT IS
A single local Flask app (127.0.0.1:5555) that is the editorial interface for the 11ty
Bundle. Three surfaces: a Social Posting page that cross-posts to Mastodon, Bluesky, and
Discord; a Bundle Entry Editor for creating/editing bundledb.json entries; and a Database
Management page. Purpose-built for one editor's machine, with access to sibling project
dirs — not for general deployment.

WORKFLOW
1. Start the app: `source .venv/bin/activate && python app.py`  (http://127.0.0.1:5555)
2. Compose/post, edit entries, or run build/deploy from the editor's Save & Run Latest /
   Save & Deploy buttons.
3. Run tests after changes: `source .venv/bin/activate && pytest` (277 tests).

SKILLS
- verify-site (skill) — Runs a fresh 11ty Bundle build, then parses the static _site output to confirm recently added entries rendered correctly (defaults to the latest issue; accepts a date / today / yesterday / latest).
EOF

jq -nc --arg m "$MESSAGE" '{systemMessage: $m}'
