from services.og_image import derive_og_image_path


def test_derive_valid_path():
    assert derive_og_image_path("/screenshots/example-com-large.jpg") == "/og-images/example-com-og.jpg"


def test_derive_with_subdomain_dashes():
    assert (
        derive_og_image_path("/screenshots/cv-kylereddoch-me-large.jpg")
        == "/og-images/cv-kylereddoch-me-og.jpg"
    )


def test_derive_empty_string():
    assert derive_og_image_path("") == ""


def test_derive_none():
    assert derive_og_image_path(None) == ""


def test_derive_unexpected_prefix():
    assert derive_og_image_path("/img/example-com-large.jpg") == ""


def test_derive_unexpected_suffix():
    # Older entries use plain .jpg without the -large suffix; refuse to derive.
    assert derive_og_image_path("/screenshots/cool11ty-dev.jpg") == ""
