import config
from platforms.discord_client import DiscordClient


class DiscordContentClient(DiscordClient):
    name = "discord_content"
    char_limit = 2000

    def __init__(self):
        super().__init__(
            webhook_url=config.DISCORD_WEBHOOK_URL_CONTENT,
            guild_id=config.DISCORD_GUILD_ID_CONTENT,
            name="discord_content",
        )
