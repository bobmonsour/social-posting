from mastodon import Mastodon
from platforms.base import PlatformClient, PostResult
import config


class MastodonClient(PlatformClient):
    name = "mastodon"
    char_limit = 500

    def __init__(self):
        self.instance_url = config.MASTODON_INSTANCE_URL
        self.access_token = config.MASTODON_ACCESS_TOKEN
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = Mastodon(
                access_token=self.access_token,
                api_base_url=self.instance_url,
            )
        return self._client

    def validate_credentials(self):
        return config.mastodon_configured()

    def post(self, text, media=None, content_warning=None, link_card=None):
        try:
            client = self._get_client()

            media_ids = []
            if media:
                for attachment in media:
                    uploaded = client.media_post(
                        media_file=attachment.file_path,
                        description=attachment.alt_text or None,
                    )
                    media_ids.append(uploaded)

            kwargs = {
                "status": text,
                "visibility": "public",
            }
            if media_ids:
                kwargs["media_ids"] = media_ids
            if content_warning:
                kwargs["spoiler_text"] = content_warning

            status = client.status_post(**kwargs)
            return PostResult(
                platform=self.name,
                success=True,
                post_url=status["url"],
            )
        except Exception as e:
            return PostResult(
                platform=self.name,
                success=False,
                error=str(e),
            )
