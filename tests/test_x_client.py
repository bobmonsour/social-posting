from unittest.mock import MagicMock, patch

import pytest

from platforms.x_client import XClient


@pytest.fixture
def x_client():
    with patch("platforms.x_client.config") as mock_config:
        mock_config.X_API_KEY = "test-key"
        mock_config.X_API_SECRET = "test-secret"
        mock_config.X_ACCESS_TOKEN = "test-token"
        mock_config.X_ACCESS_TOKEN_SECRET = "test-token-secret"
        mock_config.x_configured.return_value = True
        client = XClient()
        yield client


def test_name_and_char_limit():
    client = XClient()
    assert client.name == "x"
    assert client.char_limit == 280


def test_validate_credentials_configured(x_client):
    assert x_client.validate_credentials() is True


def test_validate_credentials_not_configured():
    with patch("platforms.x_client.config") as mock_config:
        mock_config.x_configured.return_value = False
        client = XClient()
        assert client.validate_credentials() is False


@patch("platforms.x_client.tweepy")
def test_post_text_only(mock_tweepy, x_client):
    mock_client = MagicMock()
    mock_tweepy.Client.return_value = mock_client
    mock_client.create_tweet.return_value = MagicMock(data={"id": "123456"})
    mock_client.get_me.return_value = MagicMock(data=MagicMock(username="testuser"))

    result = x_client.post("Hello from X!")

    mock_client.create_tweet.assert_called_once_with(text="Hello from X!", media_ids=None)
    assert result.success is True
    assert result.platform == "x"
    assert result.post_url == "https://x.com/testuser/status/123456"


@patch("platforms.x_client.tweepy")
def test_post_with_media(mock_tweepy, x_client, tmp_path):
    mock_client_v2 = MagicMock()
    mock_api_v1 = MagicMock()
    mock_tweepy.Client.return_value = mock_client_v2
    mock_tweepy.OAuth1UserHandler.return_value = MagicMock()
    mock_tweepy.API.return_value = mock_api_v1

    mock_upload = MagicMock()
    mock_upload.media_id = 999
    mock_api_v1.media_upload.return_value = mock_upload
    mock_client_v2.create_tweet.return_value = MagicMock(data={"id": "789"})
    mock_client_v2.get_me.return_value = MagicMock(data=MagicMock(username="testuser"))

    # Create a temp image file
    img = tmp_path / "test.png"
    img.write_bytes(b"fakepng")

    from platforms.base import MediaAttachment
    media = [MediaAttachment(file_path=str(img), mime_type="image/png", alt_text="test")]

    result = x_client.post("Post with image", media=media)

    mock_api_v1.media_upload.assert_called_once_with(filename=str(img))
    mock_client_v2.create_tweet.assert_called_once_with(text="Post with image", media_ids=[999])
    assert result.success is True
    assert result.post_url == "https://x.com/testuser/status/789"


@patch("platforms.x_client.tweepy")
def test_post_with_link_card(mock_tweepy, x_client):
    mock_client = MagicMock()
    mock_tweepy.Client.return_value = mock_client
    mock_client.create_tweet.return_value = MagicMock(data={"id": "456"})
    mock_client.get_me.return_value = MagicMock(data=MagicMock(username="testuser"))

    from platforms.base import LinkCard
    link = LinkCard(url="https://example.com/article", title="Test")

    result = x_client.post("Check this out", link_card=link)

    mock_client.create_tweet.assert_called_once_with(
        text="Check this out\n\nhttps://example.com/article",
        media_ids=None,
    )
    assert result.success is True


@patch("platforms.x_client.tweepy")
def test_post_with_link_card_already_in_text(mock_tweepy, x_client):
    mock_client = MagicMock()
    mock_tweepy.Client.return_value = mock_client
    mock_client.create_tweet.return_value = MagicMock(data={"id": "456"})
    mock_client.get_me.return_value = MagicMock(data=MagicMock(username="testuser"))

    from platforms.base import LinkCard
    link = LinkCard(url="https://example.com/article", title="Test")

    result = x_client.post("Check https://example.com/article out", link_card=link)

    mock_client.create_tweet.assert_called_once_with(
        text="Check https://example.com/article out",
        media_ids=None,
    )
    assert result.success is True


@patch("platforms.x_client.tweepy")
def test_post_failure(mock_tweepy, x_client):
    mock_client = MagicMock()
    mock_tweepy.Client.return_value = mock_client
    mock_client.create_tweet.side_effect = Exception("API rate limit")

    result = x_client.post("This will fail")

    assert result.success is False
    assert result.platform == "x"
    assert "API rate limit" in result.error


@patch("platforms.x_client.tweepy")
def test_content_warning_ignored(mock_tweepy, x_client):
    """X doesn't support content warnings, so they should be ignored."""
    mock_client = MagicMock()
    mock_tweepy.Client.return_value = mock_client
    mock_client.create_tweet.return_value = MagicMock(data={"id": "111"})
    mock_client.get_me.return_value = MagicMock(data=MagicMock(username="testuser"))

    result = x_client.post("Test post", content_warning="Sexual")

    # Content warning param is accepted but not used
    mock_client.create_tweet.assert_called_once_with(text="Test post", media_ids=None)
    assert result.success is True
