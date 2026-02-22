---
name: verify-site
description: Verify that recently added 11ty Bundle entries rendered correctly in the build output. Always runs a fresh build, then checks the static _site directory.
argument-hint: "[date or 'today' or 'yesterday' or 'latest', default: latest issue]"
disable-model-invocation: true
allowed-tools: Bash(python3 *), Bash(cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev && npm run latest), Bash(lsof *), Bash(kill *), Bash(cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb && git *)
---

## Verify Site Build

Verify that recently added entries in the 11ty Bundle build output rendered correctly by parsing the static `_site` directory. No browser required.

### Step 1: Resolve what to verify

- **Argument**: `$ARGUMENTS`
- If empty or `latest`: verify entries with the highest issue number in bundledb (default).
- If `today`, `yesterday`, or a `YYYY-MM-DD` date: verify entries matching that date.

### Step 2: Build the site (always fresh)

First, kill any existing server on port 8080 to ensure a fresh build with the latest data:

```bash
lsof -ti:8080 | xargs kill 2>/dev/null || true
```

Then start a new Eleventy build:

```bash
cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev && npm run latest
```

Run this via the Bash tool with `run_in_background: true`. Then poll until the server is ready:

```bash
python3 -c "
import urllib.request, time, sys
for i in range(20):
    try:
        urllib.request.urlopen('http://localhost:8080', timeout=3)
        print(f'Server up after {(i+1)*3} seconds')
        sys.exit(0)
    except Exception:
        time.sleep(3)
print('Timeout waiting for server')
sys.exit(1)
"
```

If it doesn't come up after 60 seconds, report the failure and stop.

### Step 3: Run verification

Run the verification script from the `social-posting` project directory:

- **Latest issue** (default): `python3 -m services.verify_site`
- **By date**: `python3 -m services.verify_site YYYY-MM-DD`

The script parses `_site/index.html` and `_site/showcase/index.html` to check:
- **Blog posts**: title present in "From the firehose" section, favicon file exists
- **Sites**: title present in "Recent sites" section, favicon file exists
- **Sites on showcase**: card found, favicon file exists, screenshot file exists
- **Releases**: title present in "Recent releases" section

Starters are excluded — they sort by GitHub modification date, not by bundledb date.

### Step 4: Commit and push on success

If verification failed, skip this step.

If verification passed (exit code 0), check for changes in the 11tybundledb repo first:

```bash
cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb && git status --porcelain
```

If the output is empty, report "No DB changes to commit" and skip the commit.

If there are changes, commit and push:

```bash
cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb && git add -A && git commit -m "New entries saved" && git push
```

### Step 5: Report

Print the verification output and git result. The verification script produces the formatted report.
