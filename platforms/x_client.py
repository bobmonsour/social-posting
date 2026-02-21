import tweepy
from platforms.base import PlatformClient, PostResult
import config


class XClient(PlatformClient):
    name = "x"
    char_limit = 280

    def __init__(self):
        self._client_v2 = None
        self._api_v1 = None

    def _get_client_v2(self):
        if self._client_v2 is None:
            self._client_v2 = tweepy.Client(
                consumer_key=config.X_API_KEY,
                consumer_secret=config.X_API_SECRET,
                access_token=config.X_ACCESS_TOKEN,
                access_token_secret=config.X_ACCESS_TOKEN_SECRET,
            )
        return self._client_v2

    def _get_api_v1(self):
        if self._api_v1 is None:
            auth = tweepy.OAuth1UserHandler(
                config.X_API_KEY,
                config.X_API_SECRET,
                config.X_ACCESS_TOKEN,
                config.X_ACCESS_TOKEN_SECRET,
            )
            self._api_v1 = tweepy.API(auth)
        return self._api_v1

    def validate_credentials(self):
        return config.x_configured()

    def post(self, text, media=None, content_warning=None, link_card=None):
        try:
            client = self._get_client_v2()

            # Append link card URL if not already in text (X auto-previews)
            if link_card and link_card.url and link_card.url not in text:
                text = f"{text}\n\n{link_card.url}"

            media_ids = None
            if media:
                api = self._get_api_v1()
                media_ids = []
                for attachment in media:
                    upload = api.media_upload(
                        filename=attachment.file_path,
                    )
                    media_ids.append(upload.media_id)

            response = client.create_tweet(
                text=text,
                media_ids=media_ids if media_ids else None,
            )

            tweet_id = response.data["id"]
            # Get the authenticated user's username for the post URL
            user = client.get_me()
            username = user.data.username
            post_url = f"https://x.com/{username}/status/{tweet_id}"

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
