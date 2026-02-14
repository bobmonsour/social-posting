# Adding Discord Posting to Social-Posting

This document is an implementation plan for adding Discord as a third posting platform alongside Mastodon and Bluesky.

## Overview

Discord supports posting messages to a specific channel on a specific server via **webhooks**. A webhook is a URL that, when POSTed to, delivers a message to the channel it was created for. This is the right approach for social-posting because:

- **No bot required** — webhooks don't need a bot user account, OAuth flow, or server permissions beyond creating the webhook.
- **Synchronous** — a simple HTTP POST, no async/await needed. Fits the existing Flask request cycle.
- **No new dependencies** — uses `requests`, which is already a transitive dependency.
- **One webhook = one channel** — configuration is a single URL, matching the simplicity of the existing platform configs.

Alternatives considered and rejected:
- **Bot token + discord.py**: Requires async code (`discord.py` is fully async), a bot user invited to the server, and `SEND_MESSAGES` permissions. Overkill for one-way posting.
- **OAuth 2.0**: Designed for user auth flows, not server-to-channel posting.

## Discord Webhook Basics

### What is a webhook?

A webhook URL is tied to a specific channel on a specific Discord server. Anyone with the URL can post messages to that channel. The URL format is:

```
https://discord.com/api/webhooks/{webhook.id}/{webhook.token}
```

### How to create a webhook

1. Open the Discord server where you want to post.
2. Go to **Server Settings > Integrations > Webhooks**.
3. Click **New Webhook**.
4. Select the target channel.
5. Optionally set a name and avatar (these become the message author).
6. Click **Copy Webhook URL**.
7. Paste the URL into your `.env` file as `DISCORD_WEBHOOK_URL`.

### Limits

- **Character limit**: 2000 characters per message.
- **Rate limit**: 30 requests per 60 seconds per webhook.
- **File attachments**: up to 10 files per message, 25MB max per file.
- **Embeds**: up to 10 embeds per message.

## Configuration

Add to `.env`:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abc-xyz-token
```

## Files to Create

### `platforms/discord_client.py`

New platform client, following the exact pattern of `mastodon_client.py` and `bluesky_client.py`.

```python
import json
import requests
from platforms.base import PlatformClient, PostResult
import config


class DiscordClient(PlatformClient):
    name = "discord"
    char_limit = 2000

    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL

    def validate_credentials(self):
        return config.discord_configured()

    def post(self, text, media=None, content_warning=None, link_card=None):
        try:
            # Apply content warning using Discord spoiler syntax
            post_text = text
            if content_warning:
                post_text = f"**CW: {content_warning}**\n\n||{text}||"

            # Append link URL if present and not already in text
            # (Discord auto-generates link previews from URLs in message text)
            if link_card and link_card.url and link_card.url not in post_text:
                post_text = f"{post_text}\n\n{link_card.url}"

            # Use ?wait=true to get the message object back (for post URL)
            url = f"{self.webhook_url}?wait=true"

            if media:
                # Multipart form: files + JSON payload
                files = {}
                for i, attachment in enumerate(media):
                    files[f"files[{i}]"] = (
                        attachment.file_path.split("/")[-1],
                        open(attachment.file_path, "rb"),
                        attachment.mime_type,
                    )
                payload = {"content": post_text}
                resp = requests.post(
                    url,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                )
                # Close file handles
                for f in files.values():
                    f[1].close()
            else:
                # Simple JSON POST for text-only messages
                resp = requests.post(
                    url,
                    json={"content": post_text},
                )

            resp.raise_for_status()

            # Extract post URL from response (requires ?wait=true)
            # Jump URL format: https://discord.com/channels/{guild_id}/{channel_id}/{message_id}
            post_url = ""
            try:
                data = resp.json()
                msg_id = data.get("id", "")
                channel_id = data.get("channel_id", "")
                # guild_id is not in webhook response; omit for DM-style link
                # or use @me which works for jump links
                if msg_id and channel_id:
                    post_url = f"https://discord.com/channels/@me/{channel_id}/{msg_id}"
            except (ValueError, KeyError):
                pass

            return PostResult(
                platform=self.name,
                success=True,
                post_url=post_url,
            )
        except requests.HTTPError as e:
            return PostResult(
                platform=self.name,
                success=False,
                error=f"Discord API error: {e.response.status_code} {e.response.text}",
            )
        except Exception as e:
            return PostResult(
                platform=self.name,
                success=False,
                error=str(e),
            )
```

## Files to Modify

### `platforms/__init__.py`

```python
from platforms.mastodon_client import MastodonClient
from platforms.bluesky_client import BlueskyClient
from platforms.discord_client import DiscordClient

PLATFORMS = {
    "mastodon": MastodonClient,
    "bluesky": BlueskyClient,
    "discord": DiscordClient,
}
```

### `config.py`

Add:

```python
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def discord_configured():
    return bool(DISCORD_WEBHOOK_URL)
```

### `app.py`

- Pass `discord_available=config.discord_configured()` to templates in `compose()`, `use_draft()`, and `retry_post()`.
- In the posting loop: no special handling needed for Discord (no image compression, no link card object — URLs auto-preview, images sent as attachments).

### `templates/compose.html`

Add Discord checkbox to the Platforms fieldset:

```html
<label>
    <input type="checkbox" name="platforms" value="discord" id="cb-discord"
           {% if not discord_available %}disabled{% endif %}>
    Discord (2000 chars)
    {% if not discord_available %}<small> — not configured</small>{% endif %}
</label>
```

Add a Discord character counter in the shared textarea section:

```html
<span id="counter-discord" class="counter" hidden>Discord: <span class="count">0</span>/2000</span>
```

No content warning section needed for Discord (spoiler syntax is applied automatically by the client).

### `static/js/compose.js`

- Add `cbDiscord` and `counterDiscord` element references.
- Include Discord in `updatePlatformSections()`: toggle `counterDiscord.hidden` based on `cbDiscord.checked`.
- Add Discord counter update in `updateCharCounters()` with 2000 limit.
- Discord is automatically included in platform validation (the existing `!cbMastodon.checked && !cbBluesky.checked` check needs to become a loop or add `&& !cbDiscord.checked`).

### `modes.py` (optional)

If a mode should auto-select Discord, add `"discord"` to its `platforms` list and define a Discord-specific suffix. Discord doesn't have native hashtag or mention conventions, so the suffix might just be plain text. This is optional and can be deferred.

## Discord-Specific Behaviors

| Feature | Discord behavior |
|---|---|
| **Images** | Up to 10 files, 25MB each. No compression needed. |
| **Link previews** | Auto-generated from URLs in message text. No embed object needed. |
| **Markdown** | Discord flavor: `**bold**`, `*italic*`, `||spoiler||`, `` `code` ``, `> quote`. |
| **@mentions** | Use `<@user_id>` numeric format. Not useful for cross-posting; send as plain text. |
| **#hashtags** | Not a Discord concept. Sent as plain text. |
| **Content warnings** | No native system. Simulated with `**CW: text**\n\n\|\|spoilered content\|\|`. |
| **Post URL** | Available via `?wait=true` param. Jump URL format: `https://discord.com/channels/@me/{channel_id}/{message_id}`. |

## Post URL via `?wait=true`

By default, webhook POSTs return `204 No Content` — no message ID. Appending `?wait=true` to the webhook URL makes Discord return the full message object, including `id` and `channel_id`. This allows constructing a jump URL for the sidebar.

Trade-off: adds a small amount of response parsing, but provides a clickable link in the Recent Posts sidebar — consistent with Mastodon and Bluesky behavior. Recommended.

## Verification Steps

1. Create a test webhook on a private Discord server/channel.
2. Add `DISCORD_WEBHOOK_URL` to `.env` and restart the app.
3. Post a text-only message with Discord checked — verify it appears in the channel.
4. Post with an image — verify the image renders as an attachment in Discord.
5. Post with a URL in the URL field — verify Discord generates a link preview.
6. Check that the character counter shows `Discord: 0/2000` when Discord is checked.
7. Save a draft with Discord selected — reload — use draft — verify Discord is still checked.
8. Post to all three platforms simultaneously — verify each receives the message.
9. Simulate a failure (e.g., invalid webhook URL) — verify FAILED badge and Retry button work.
10. Test in 11ty mode — verify Discord is not auto-checked (unless added to mode config).
