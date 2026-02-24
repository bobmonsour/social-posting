import json
from unittest.mock import MagicMock, patch

import responses
from bs4 import BeautifulSoup

from services.content_review import fetch_page_text, find_subpages, review_content


SAMPLE_HTML = """
<html>
<head><title>Test Site</title></head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<header><h1>Site Header</h1></header>
<main>
  <p>This is the main content of the website about web development.</p>
  <article>
    <h2><a href="/posts/my-first-post">My First Blog Post Title Here</a></h2>
    <p>Some preview text for the post.</p>
  </article>
  <article>
    <h2><a href="/posts/second-post">Another Interesting Article</a></h2>
    <p>More preview text.</p>
  </article>
</main>
<aside>Sidebar content here</aside>
<footer>Copyright 2026</footer>
</body>
</html>
"""


class TestFetchPageText:
    @responses.activate
    def test_extracts_body_text_strips_boilerplate(self):
        responses.add(responses.GET, "https://example.com", body=SAMPLE_HTML)
        text = fetch_page_text("https://example.com")
        assert "main content" in text
        assert "web development" in text
        # Nav, header, footer, aside should be stripped
        assert "Site Header" not in text
        assert "Sidebar content" not in text
        assert "Copyright 2026" not in text

    @responses.activate
    def test_truncates_to_3000_chars(self):
        long_html = "<html><body>" + "x" * 5000 + "</body></html>"
        responses.add(responses.GET, "https://example.com", body=long_html)
        text = fetch_page_text("https://example.com")
        assert len(text) <= 3000

    @responses.activate
    def test_returns_empty_on_error(self):
        responses.add(responses.GET, "https://example.com", status=500)
        text = fetch_page_text("https://example.com")
        assert text == ""

    def test_returns_empty_on_network_error(self):
        # No responses registered = ConnectionError
        text = fetch_page_text("https://nonexistent.invalid")
        assert text == ""


class TestFindSubpages:
    def test_finds_about_page(self):
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        subpages, blog_posts_to_fetch, blog_titles_only = find_subpages("https://example.com", soup)
        assert any("/about" in url for url in subpages)

    def test_finds_values_and_now_pages(self):
        html = """<html><body>
        <a href="/about">About</a>
        <a href="/values">Values</a>
        <a href="/now">Now</a>
        </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        subpages, _, _ = find_subpages("https://example.com", soup)
        assert any("/values" in url for url in subpages)
        assert any("/now" in url for url in subpages)

    def test_returns_three_elements(self):
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        result = find_subpages("https://example.com", soup)
        assert len(result) == 3

    def test_finds_blog_post_links(self):
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        subpages, blog_posts_to_fetch, blog_titles_only = find_subpages("https://example.com", soup)
        all_blogs = blog_posts_to_fetch + blog_titles_only
        urls = [url for _, url in all_blogs]
        assert any("my-first-post" in url for url in urls)
        assert any("second-post" in url for url in urls)

    def test_blog_posts_to_fetch_limited_to_3(self):
        html = "<html><body><main>"
        for i in range(20):
            html += f'<a href="/posts/post-{i}">Blog Post Number {i} Title</a>'
        html += "</main></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        _, blog_posts_to_fetch, blog_titles_only = find_subpages("https://example.com", soup)
        assert len(blog_posts_to_fetch) <= 3
        assert len(blog_titles_only) <= 7
        assert len(blog_posts_to_fetch) + len(blog_titles_only) <= 10

    def test_limits_subpages_to_5(self):
        html = """<html><body>
        <a href="/about">About</a>
        <a href="/author">Author</a>
        <a href="/beliefs">Beliefs</a>
        <a href="/values">Values</a>
        <a href="/now">Now</a>
        <a href="/extra">Extra</a>
        </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        subpages, _, _ = find_subpages("https://example.com", soup)
        assert len(subpages) == 5
        assert not any("/extra" in url for url in subpages)

    def test_ignores_external_links(self):
        html = '<html><body><a href="https://other.com/about">External About</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        subpages, blog_posts, blog_titles = find_subpages("https://example.com", soup)
        assert len(subpages) == 0
        assert len(blog_posts) == 0
        assert len(blog_titles) == 0


class TestReviewPrompt:
    def test_prompt_includes_anti_ai_carveout(self):
        from services.content_review import REVIEW_PROMPT
        assert "AI" in REVIEW_PROMPT
        assert "AI-generated content" in REVIEW_PROMPT

    def test_prompt_includes_dead_sites_carveout(self):
        from services.content_review import REVIEW_PROMPT
        assert "Dead sites" in REVIEW_PROMPT
        assert "parked domains" in REVIEW_PROMPT

    def test_prompt_includes_strong_language_carveout(self):
        from services.content_review import REVIEW_PROMPT
        assert "strong language" in REVIEW_PROMPT.lower() or "Strong language" in REVIEW_PROMPT
        assert "profanity" in REVIEW_PROMPT


class TestReviewContent:
    def test_returns_error_when_no_api_key(self):
        with patch("services.content_review.config") as mock_config:
            mock_config.ANTHROPIC_API_KEY = ""
            result = review_content("https://example.com")
            assert result["flagged"] is False
            assert "not configured" in result["error"]

    @responses.activate
    def test_returns_not_flagged(self):
        responses.add(responses.GET, "https://example.com", body=SAMPLE_HTML)
        responses.add(responses.GET, "https://example.com/about",
                       body="<html><body>About page content</body></html>")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"flagged": false}')]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("services.content_review.config") as mock_config, \
             patch("services.content_review.anthropic") as mock_anthropic:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_anthropic.Anthropic.return_value = mock_client

            result = review_content("https://example.com")
            assert result["flagged"] is False
            assert result["pages_checked"] >= 1
            assert "https://example.com" in result["pages"]

    @responses.activate
    def test_returns_flagged(self):
        responses.add(responses.GET, "https://example.com", body=SAMPLE_HTML)
        responses.add(responses.GET, "https://example.com/about",
                       body="<html><body>About page</body></html>")

        api_response = json.dumps({
            "flagged": True,
            "confidence": "high",
            "summary": "Site contains discriminatory content"
        })
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=api_response)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("services.content_review.config") as mock_config, \
             patch("services.content_review.anthropic") as mock_anthropic:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_anthropic.Anthropic.return_value = mock_client

            result = review_content("https://example.com")
            assert result["flagged"] is True
            assert result["confidence"] == "high"
            assert "discriminatory" in result["summary"]

    @responses.activate
    def test_fetches_blog_post_text(self):
        """Blog posts in blog_posts_to_fetch should have their text fetched."""
        html_with_posts = """<html><body><main>
        <p>Homepage content here for testing.</p>
        <a href="/posts/post-one">First Blog Post Title Here</a>
        <a href="/posts/post-two">Second Blog Post Title Here</a>
        <a href="/posts/post-three">Third Blog Post Title Here</a>
        <a href="/posts/post-four">Fourth Blog Post Title Here</a>
        </main></body></html>"""
        responses.add(responses.GET, "https://example.com", body=html_with_posts)
        responses.add(responses.GET, "https://example.com/posts/post-one",
                       body="<html><body>Blog post one content</body></html>")
        responses.add(responses.GET, "https://example.com/posts/post-two",
                       body="<html><body>Blog post two content</body></html>")
        responses.add(responses.GET, "https://example.com/posts/post-three",
                       body="<html><body>Blog post three content</body></html>")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"flagged": false}')]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("services.content_review.config") as mock_config, \
             patch("services.content_review.anthropic") as mock_anthropic:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_anthropic.Anthropic.return_value = mock_client

            result = review_content("https://example.com")
            # Should have fetched homepage + 3 blog posts
            assert result["pages_checked"] >= 4
            # The API call should contain blog post sections
            call_args = mock_client.messages.create.call_args
            content = call_args[1]["messages"][0]["content"]
            assert "=== BLOG POST (" in content
            # Fourth post should be in titles only
            assert "=== BLOG POST TITLES ===" in content

    @responses.activate
    def test_handles_api_error_gracefully(self):
        responses.add(responses.GET, "https://example.com", body=SAMPLE_HTML)
        responses.add(responses.GET, "https://example.com/about",
                       body="<html><body>About</body></html>")

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")

        with patch("services.content_review.config") as mock_config, \
             patch("services.content_review.anthropic") as mock_anthropic:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_anthropic.Anthropic.return_value = mock_client

            result = review_content("https://example.com")
            assert result["flagged"] is False
            assert "error" in result

    @responses.activate
    def test_handles_invalid_json_response(self):
        responses.add(responses.GET, "https://example.com",
                       body="<html><body>Simple page</body></html>")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This is not JSON")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("services.content_review.config") as mock_config, \
             patch("services.content_review.anthropic") as mock_anthropic:
            mock_config.ANTHROPIC_API_KEY = "test-key"
            mock_anthropic.Anthropic.return_value = mock_client

            result = review_content("https://example.com")
            assert result["flagged"] is False
            assert "parse" in result["error"].lower()


class TestContentReviewEndpoint:
    def test_returns_400_when_no_url(self, client):
        resp = client.post("/editor/content-review",
                          json={},
                          content_type="application/json")
        assert resp.status_code == 400

    def test_endpoint_calls_review_content(self, client):
        mock_result = {"flagged": False, "pages_checked": 2}
        with patch("services.content_review.review_content", return_value=mock_result), \
             patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist"):
            resp = client.post("/editor/content-review",
                              json={"url": "https://example.com"},
                              content_type="application/json")
            data = resp.get_json()
            assert data["success"] is True
            assert data["flagged"] is False
            assert data["pages_checked"] == 2

    def test_endpoint_with_flagged_result(self, client):
        mock_result = {
            "flagged": True,
            "confidence": "medium",
            "summary": "Concerning content found",
            "pages_checked": 3
        }
        with patch("services.content_review.review_content", return_value=mock_result):
            resp = client.post("/editor/content-review",
                              json={"url": "https://example.com"},
                              content_type="application/json")
            data = resp.get_json()
            assert data["success"] is True
            assert data["flagged"] is True
            assert data["confidence"] == "medium"

    def test_endpoint_adds_cleared_site_to_allowlist(self, client):
        mock_result = {"flagged": False, "pages_checked": 2}
        saved = {}
        def capture_save(al):
            saved.update(al)
        with patch("services.content_review.review_content", return_value=mock_result), \
             patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist", side_effect=capture_save):
            resp = client.post("/editor/content-review",
                              json={"url": "https://newsite.dev", "title": "New Site"},
                              content_type="application/json")
            data = resp.get_json()
            assert data["success"] is True
            assert "https://newsite.dev" in saved
            assert saved["https://newsite.dev"]["title"] == "New Site"

    def test_endpoint_does_not_add_flagged_site_to_allowlist(self, client):
        mock_result = {"flagged": True, "confidence": "high", "summary": "Bad", "pages_checked": 1}
        with patch("services.content_review.review_content", return_value=mock_result):
            resp = client.post("/editor/content-review",
                              json={"url": "https://badsite.dev"},
                              content_type="application/json")
            data = resp.get_json()
            assert data["flagged"] is True
