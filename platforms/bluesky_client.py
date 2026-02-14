import re
from datetime import datetime, timezone

from atproto import Client, models
from platforms.base import PlatformClient, PostResult
import config


# Regex patterns for facet detection
URL_PATTERN = re.compile(
    r"https?://[^\s\)\]\}>\"',]+[^\s\)\]\}>\"',.\!?]"
)
MENTION_PATTERN = re.compile(
    r"(?<!\w)@([\w.]+(?:\.[\w]+)+)"
)
HASHTAG_PATTERN = re.compile(
    r"(?<!\w)#(\w+)"
)


def parse_facets(text):
    """Parse URLs, mentions, and hashtags from text to create Bluesky facets."""
    facets = []
    text_bytes = text.encode("utf-8")

    for match in URL_PATTERN.finditer(text):
        start = len(text[: match.start()].encode("utf-8"))
        end = len(text[: match.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=start, byte_end=end
                ),
                features=[
                    models.AppBskyRichtextFacet.Link(uri=match.group(0))
                ],
            )
        )

    for match in MENTION_PATTERN.finditer(text):
        start = len(text[: match.start()].encode("utf-8"))
        end = len(text[: match.end()].encode("utf-8"))
        # Use the handle as-is; resolution would require an API call
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=start, byte_end=end
                ),
                features=[
                    models.AppBskyRichtextFacet.Mention(did=match.group(1))
                ],
            )
        )

    for match in HASHTAG_PATTERN.finditer(text):
        start = len(text[: match.start()].encode("utf-8"))
        end = len(text[: match.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=start, byte_end=end
                ),
                features=[
                    models.AppBskyRichtextFacet.Tag(tag=match.group(1))
                ],
            )
        )

    return facets if facets else None


def resolve_handle(client, handle):
    """Resolve a handle to a DID for mentions."""
    try:
        resp = client.resolve_handle(handle)
        return resp.did
    except Exception:
        return None


class BlueskyClient(PlatformClient):
    name = "bluesky"
    char_limit = 300

    def __init__(self):
        self.identifier = config.BLUESKY_IDENTIFIER
        self.app_password = config.BLUESKY_APP_PASSWORD
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = Client()
            self._client.login(self.identifier, self.app_password)
        return self._client

    def validate_credentials(self):
        return config.bluesky_configured()

    def post(self, text, media=None, content_warning=None, link_card=None):
        try:
            client = self._get_client()

            # Parse facets for clickable links/mentions/hashtags
            facets = parse_facets(text)

            # Resolve mention DIDs
            if facets:
                for facet in facets:
                    for feature in facet.features:
                        if isinstance(feature, models.AppBskyRichtextFacet.Mention):
                            did = resolve_handle(client, feature.did)
                            if did:
                                feature.did = did

            embed = None

            # Handle image embeds
            if media:
                images = []
                for attachment in media:
                    with open(attachment.file_path, "rb") as f:
                        img_data = f.read()
                    upload = client.upload_blob(img_data)
                    images.append(
                        models.AppBskyEmbedImages.Image(
                            alt=attachment.alt_text or "",
                            image=upload.blob,
                        )
                    )
                embed = models.AppBskyEmbedImages.Main(images=images)

            # Handle link card embed (mutually exclusive with images)
            elif link_card:
                thumb_blob = None
                if link_card.image_data:
                    upload = client.upload_blob(link_card.image_data)
                    thumb_blob = upload.blob
                embed = models.AppBskyEmbedExternal.Main(
                    external=models.AppBskyEmbedExternal.External(
                        uri=link_card.url,
                        title=link_card.title or "",
                        description=link_card.description or "",
                        thumb=thumb_blob,
                    )
                )

            # Build the post record
            record = models.AppBskyFeedPost.Record(
                text=text,
                facets=facets,
                embed=embed,
                created_at=client.get_current_time_iso(),
            )

            # Add content labels if specified
            if content_warning and content_warning in (
                "sexual",
                "nudity",
                "graphic-media",
                "porn",
            ):
                record.labels = models.ComAtprotoLabelDefs.SelfLabels(
                    values=[
                        models.ComAtprotoLabelDefs.SelfLabel(val=content_warning)
                    ]
                )

            response = client.com.atproto.repo.create_record(
                models.ComAtprotoRepoCreateRecord.Data(
                    repo=client.me.did,
                    collection=models.ids.AppBskyFeedPost,
                    record=record,
                )
            )

            # Build the post URL from the response
            # URI format: at://did:plc:.../app.bsky.feed.post/rkey
            rkey = response.uri.split("/")[-1]
            handle = self.identifier
            post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

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
