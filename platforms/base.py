from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MediaAttachment:
    file_path: str
    mime_type: str
    alt_text: str = ""


@dataclass
class LinkCard:
    url: str
    title: str = ""
    description: str = ""
    image_url: str = ""
    image_data: bytes = field(default=b"", repr=False)
    image_mime: str = ""


@dataclass
class PostResult:
    platform: str
    success: bool
    post_url: str = ""
    error: str = ""


class PlatformClient(ABC):
    name: str = ""
    char_limit: int = 500

    @abstractmethod
    def post(self, text, media=None, content_warning=None, link_card=None):
        """Post content to the platform. Returns a PostResult."""
        pass

    @abstractmethod
    def validate_credentials(self):
        """Check if credentials are configured. Returns bool."""
        pass
