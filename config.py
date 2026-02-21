import os
from dotenv import load_dotenv

load_dotenv()

MASTODON_INSTANCE_URL = os.getenv("MASTODON_INSTANCE_URL", "").rstrip("/")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN", "")

BLUESKY_IDENTIFIER = os.getenv("BLUESKY_IDENTIFIER", "")
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
MAX_IMAGES = 4
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
BLUESKY_MAX_IMAGE_SIZE = 1_000_000  # 1MB


def mastodon_configured():
    return bool(MASTODON_INSTANCE_URL and MASTODON_ACCESS_TOKEN)


def bluesky_configured():
    return bool(BLUESKY_IDENTIFIER and BLUESKY_APP_PASSWORD)


def discord_configured():
    return bool(DISCORD_WEBHOOK_URL and DISCORD_GUILD_ID)


def x_configured():
    return bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET)
