from platforms.mastodon_client import MastodonClient
from platforms.bluesky_client import BlueskyClient
from platforms.discord_client import DiscordClient
from platforms.x_client import XClient

PLATFORMS = {
    "mastodon": MastodonClient,
    "bluesky": BlueskyClient,
    "discord": DiscordClient,
    "x": XClient,
}


def get_platform(name):
    cls = PLATFORMS.get(name)
    if cls is None:
        raise ValueError(f"Unknown platform: {name}")
    return cls()
