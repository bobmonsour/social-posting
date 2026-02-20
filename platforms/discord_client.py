import json

import requests
from platforms.base import PlatformClient, PostResult
import config


class DiscordClient(PlatformClient):
    name = "discord"
    char_limit = 2000

    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL
        self.guild_id = config.DISCORD_GUILD_ID

    def validate_credentials(self):
        return config.discord_configured()

    def post(self, text, media=None, content_warning=None, link_card=None):
        try:
            # Apply content warning using Discord spoiler syntax
            if content_warning:
                text = f"**CW: {content_warning}**\n\n||{text}||"

            # Append link card URL if not already in text (Discord auto-previews)
            if link_card and link_card.url and link_card.url not in text:
                text = f"{text}\n\n{link_card.url}"

            url = f"{self.webhook_url}?wait=true"

            if media:
                files = {}
                for i, attachment in enumerate(media):
                    files[f"file{i}"] = (
                        attachment.file_path.rsplit("/", 1)[-1],
                        open(attachment.file_path, "rb"),
                        attachment.mime_type,
                    )
                payload = {"content": text}
                resp = requests.post(
                    url,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                )
                # Close file handles
                for f in files.values():
                    f[1].close()
            else:
                resp = requests.post(
                    url,
                    json={"content": text},
                )

            if resp.status_code not in (200, 204):
                error_msg = resp.text[:200]
                return PostResult(
                    platform=self.name,
                    success=False,
                    error=f"Discord API error {resp.status_code}: {error_msg}",
                )

            data = resp.json()
            channel_id = data.get("channel_id", "")
            message_id = data.get("id", "")
            post_url = (
                f"https://discord.com/channels/{self.guild_id}/{channel_id}/{message_id}"
                if channel_id and message_id
                else ""
            )

            return PostResult(
                platform=self.name,
                success=True,
                post_url=post_url,
            )
        except Exception as e:
            return PostResult(
                platform=self.name,
                success=False,
                error=str(e),
            )
