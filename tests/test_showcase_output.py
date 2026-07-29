import pytest

from services import showcase_output
from services.showcase_output import (
    delete_showcase_output,
    showcase_output_path,
    showcase_slug_for_site,
)


@pytest.fixture
def showcase_dir(tmp_path, monkeypatch):
    """A stand-in for 11tybundle.dev/_site/showcase."""
    path = tmp_path / "_site" / "showcase"
    path.mkdir(parents=True)
    monkeypatch.setattr(showcase_output, "SHOWCASE_OUTPUT_DIR", path)
    return path


# --- showcase_slug_for_site ---

def test_slug_is_the_slugified_hostname():
    assert showcase_slug_for_site("https://alliancefutures.org/") == "alliancefutures-org"


def test_slug_ignores_the_path():
    assert showcase_slug_for_site("https://bobmonsour.com/posts/") == "bobmonsour-com"


def test_slug_keeps_www_and_multi_part_tld():
    assert showcase_slug_for_site("https://www.example.co.uk") == "www-example-co-uk"


def test_slug_is_none_for_unparseable_url():
    assert showcase_slug_for_site("not a url") is None
    assert showcase_slug_for_site("") is None


# --- showcase_output_path ---

def test_output_path_is_the_slug_under_the_showcase_dir(showcase_dir):
    assert showcase_output_path("https://cool11ty.dev") == showcase_dir / "cool11ty-dev"


def test_output_path_does_not_require_the_directory_to_exist(showcase_dir):
    assert showcase_output_path("https://never-built.dev") is not None


def test_output_path_is_none_when_there_is_no_usable_slug(showcase_dir):
    assert showcase_output_path("not a url") is None
    assert showcase_output_path("https://.../page") is None


# --- delete_showcase_output ---

def test_deletes_the_generated_page_directory(showcase_dir):
    page = showcase_dir / "cool11ty-dev"
    page.mkdir()
    (page / "index.html").write_text("<html></html>")

    result = delete_showcase_output("https://cool11ty.dev")

    assert result["status"] == "deleted"
    assert result["slug"] == "cool11ty-dev"
    assert not page.exists()


def test_leaves_other_page_directories_alone(showcase_dir):
    (showcase_dir / "cool11ty-dev").mkdir()
    (showcase_dir / "other-dev").mkdir()

    delete_showcase_output("https://cool11ty.dev")

    assert (showcase_dir / "other-dev").exists()


def test_missing_directory_is_not_an_error(showcase_dir):
    result = delete_showcase_output("https://never-built.dev")

    assert result["status"] == "not_found"
    assert result["slug"] == "never-built-dev"


def test_unparseable_url_is_reported_as_invalid(showcase_dir):
    result = delete_showcase_output("not a url")

    assert result["status"] == "invalid"
    assert showcase_dir.exists()


def test_hostname_that_slugifies_to_nothing_never_removes_the_showcase_dir(showcase_dir):
    (showcase_dir / "keep-me").mkdir()

    result = delete_showcase_output("https://.../page")

    assert result["status"] == "invalid"
    assert showcase_dir.exists()
    assert (showcase_dir / "keep-me").exists()


def test_missing_showcase_output_dir_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(showcase_output, "SHOWCASE_OUTPUT_DIR", tmp_path / "nope" / "showcase")

    result = delete_showcase_output("https://cool11ty.dev")

    assert result["status"] == "not_found"


def test_a_file_at_the_slug_path_is_not_removed(showcase_dir):
    stray = showcase_dir / "cool11ty-dev"
    stray.write_text("not a directory")

    result = delete_showcase_output("https://cool11ty.dev")

    assert result["status"] == "not_found"
    assert stray.exists()
