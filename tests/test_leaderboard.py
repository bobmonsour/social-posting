import responses

from services.leaderboard import check_leaderboard_link


@responses.activate
def test_leaderboard_found():
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com", status=200)
    result = check_leaderboard_link("https://example.com")
    assert result == "https://www.11ty.dev/speedlify/example-com/"


@responses.activate
def test_leaderboard_found_with_trailing_slash():
    # First probe (bare, no slash) fails
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com", status=404)
    # Second probe (bare, with slash) succeeds
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com/", status=200)
    result = check_leaderboard_link("https://example.com")
    assert result == "https://www.11ty.dev/speedlify/example-com/"


@responses.activate
def test_leaderboard_www_stripped():
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com", status=200)
    result = check_leaderboard_link("https://www.example.com")
    assert result is not None
    assert "example-com" in result


@responses.activate
def test_leaderboard_dot_to_hyphen():
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/my-site-dev", status=200)
    result = check_leaderboard_link("https://my.site.dev")
    assert result == "https://www.11ty.dev/speedlify/my-site-dev/"


@responses.activate
def test_leaderboard_www_variant():
    # Bare domain fails
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com", status=404)
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/example-com/", status=404)
    # www variant succeeds
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/www-example-com", status=200)
    result = check_leaderboard_link("https://example.com")
    assert result == "https://www.11ty.dev/speedlify/www-example-com/"


@responses.activate
def test_leaderboard_not_found():
    # All probes fail
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/nowhere-com", status=404)
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/nowhere-com/", status=404)
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/www-nowhere-com", status=404)
    responses.add(responses.HEAD, "https://www.11ty.dev/speedlify/www-nowhere-com/", status=404)
    assert check_leaderboard_link("https://nowhere.com") is None


def test_leaderboard_empty_url():
    assert check_leaderboard_link("") is None
