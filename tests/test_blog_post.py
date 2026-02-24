import os
from unittest.mock import MagicMock, patch

import responses

from services.blog_post import summarize_blog_post, create_blog_post


SAMPLE_HTML = """
<html><body>
<main><p>This is a detailed blog post about building accessible web components
with Eleventy and discussing best practices for semantic HTML markup.</p></main>
</body></html>
"""


class TestSummarizeBlogPost:
    @responses.activate
    @patch("services.blog_post.config")
    @patch("services.blog_post.anthropic")
    def test_returns_summary(self, mock_anthropic, mock_config):
        mock_config.ANTHROPIC_API_KEY = "test-key"
        responses.add(responses.GET, "https://example.com/post", body=SAMPLE_HTML)

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="A post about building accessible web components with Eleventy.")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client

        result = summarize_blog_post("https://example.com/post")
        assert result == "A post about building accessible web components with Eleventy."
        mock_client.messages.create.assert_called_once()

    @responses.activate
    @patch("services.blog_post.config")
    @patch("services.blog_post.anthropic")
    def test_strips_code_fences(self, mock_anthropic, mock_config):
        mock_config.ANTHROPIC_API_KEY = "test-key"
        responses.add(responses.GET, "https://example.com/post", body=SAMPLE_HTML)

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="```\nA summary sentence.\n```")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client

        result = summarize_blog_post("https://example.com/post")
        assert result == "A summary sentence."

    @responses.activate
    @patch("services.blog_post.config")
    def test_returns_unavailable_on_fetch_error(self, mock_config):
        mock_config.ANTHROPIC_API_KEY = "test-key"
        responses.add(responses.GET, "https://example.com/post", status=500)

        result = summarize_blog_post("https://example.com/post")
        assert result == "[summary unavailable]"

    @patch("services.blog_post.config")
    def test_returns_unavailable_without_api_key(self, mock_config):
        mock_config.ANTHROPIC_API_KEY = ""
        result = summarize_blog_post("https://example.com/post")
        assert result == "[summary unavailable]"

    @responses.activate
    @patch("services.blog_post.config")
    @patch("services.blog_post.anthropic")
    def test_returns_unavailable_on_api_error(self, mock_anthropic, mock_config):
        mock_config.ANTHROPIC_API_KEY = "test-key"
        responses.add(responses.GET, "https://example.com/post", body=SAMPLE_HTML)

        mock_anthropic.Anthropic.return_value.messages.create.side_effect = Exception("API error")

        result = summarize_blog_post("https://example.com/post")
        assert result == "[summary unavailable]"

    @responses.activate
    @patch("services.blog_post.config")
    def test_returns_unavailable_on_short_text(self, mock_config):
        mock_config.ANTHROPIC_API_KEY = "test-key"
        responses.add(responses.GET, "https://example.com/post", body="<html><body>Hi</body></html>")

        result = summarize_blog_post("https://example.com/post")
        assert result == "[summary unavailable]"


class TestCreateBlogPostHighlights:
    def test_highlight_with_summary(self, tmp_path):
        # Create template
        template = tmp_path / "template.md"
        template.write_text(
            "---\nbundleIssue:\ndate:\n---\n\n## Highlights\n\n**.**\n\n**.**\n\n**.**\n"
        )
        blog_dir = tmp_path / "blog" / "2026"
        blog_dir.mkdir(parents=True)

        import services.blog_post as bp
        orig_template = bp._TEMPLATE_PATH
        orig_blog = bp._BLOG_BASE_PATH
        bp._TEMPLATE_PATH = str(template)
        bp._BLOG_BASE_PATH = str(tmp_path / "blog")

        try:
            result = create_blog_post(1, "2026-02-24", highlights=[
                {
                    "author": "Alice",
                    "author_site": "https://alice.dev",
                    "title": "My Post",
                    "link": "https://alice.dev/post",
                    "summary": "A post about web components.",
                },
            ])
            assert result["success"]
            content = open(result["file_path"]).read()
            assert "**.** [Alice](https://alice.dev) - [My Post](https://alice.dev/post) — A post about web components." in content
        finally:
            bp._TEMPLATE_PATH = orig_template
            bp._BLOG_BASE_PATH = orig_blog

    def test_highlight_without_summary(self, tmp_path):
        template = tmp_path / "template.md"
        template.write_text(
            "---\nbundleIssue:\ndate:\n---\n\n## Highlights\n\n**.**\n\n**.**\n\n**.**\n"
        )
        blog_dir = tmp_path / "blog" / "2026"
        blog_dir.mkdir(parents=True)

        import services.blog_post as bp
        orig_template = bp._TEMPLATE_PATH
        orig_blog = bp._BLOG_BASE_PATH
        bp._TEMPLATE_PATH = str(template)
        bp._BLOG_BASE_PATH = str(tmp_path / "blog")

        try:
            result = create_blog_post(1, "2026-02-24", highlights=[
                {
                    "author": "Bob",
                    "author_site": "https://bob.dev",
                    "title": "Another Post",
                    "link": "https://bob.dev/post",
                },
            ])
            assert result["success"]
            content = open(result["file_path"]).read()
            assert "**.** [Bob](https://bob.dev) - [Another Post](https://bob.dev/post)\n" in content
            # No em dash should appear
            assert " — " not in content
        finally:
            bp._TEMPLATE_PATH = orig_template
            bp._BLOG_BASE_PATH = orig_blog


class TestCreateBlogPostOverwrite:
    def test_exists_returns_error_with_exists_flag(self, tmp_path):
        template = tmp_path / "template.md"
        template.write_text("---\nbundleIssue:\ndate:\n---\n")
        blog_dir = tmp_path / "blog" / "2026"
        blog_dir.mkdir(parents=True)
        (blog_dir / "11ty-bundle-01.md").write_text("existing")

        import services.blog_post as bp
        orig_template, orig_blog = bp._TEMPLATE_PATH, bp._BLOG_BASE_PATH
        bp._TEMPLATE_PATH = str(template)
        bp._BLOG_BASE_PATH = str(tmp_path / "blog")

        try:
            result = create_blog_post(1, "2026-02-24")
            assert not result["success"]
            assert result["exists"] is True
            assert "already exists" in result["error"]
        finally:
            bp._TEMPLATE_PATH = orig_template
            bp._BLOG_BASE_PATH = orig_blog

    def test_overwrite_replaces_existing_file(self, tmp_path):
        template = tmp_path / "template.md"
        template.write_text("---\nbundleIssue:\ndate:\n---\n")
        blog_dir = tmp_path / "blog" / "2026"
        blog_dir.mkdir(parents=True)
        (blog_dir / "11ty-bundle-01.md").write_text("old content")

        import services.blog_post as bp
        orig_template, orig_blog = bp._TEMPLATE_PATH, bp._BLOG_BASE_PATH
        bp._TEMPLATE_PATH = str(template)
        bp._BLOG_BASE_PATH = str(tmp_path / "blog")

        try:
            result = create_blog_post(1, "2026-02-24", overwrite=True)
            assert result["success"]
            content = open(result["file_path"]).read()
            assert "bundleIssue: 1" in content
            assert "old content" not in content
        finally:
            bp._TEMPLATE_PATH = orig_template
            bp._BLOG_BASE_PATH = orig_blog
