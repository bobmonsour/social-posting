from app import showcase_url_for_site


def test_basic_hostname():
    assert (showcase_url_for_site("https://alliancefutures.org/")
            == "https://11tybundle.dev/showcase/alliancefutures-org/")


def test_path_is_ignored_only_hostname_used():
    assert (showcase_url_for_site("https://bobmonsour.com/posts/")
            == "https://11tybundle.dev/showcase/bobmonsour-com/")


def test_www_and_multi_part_tld_preserved():
    assert (showcase_url_for_site("https://www.example.co.uk")
            == "https://11tybundle.dev/showcase/www-example-co-uk/")


def test_unparseable_url_returns_none():
    assert showcase_url_for_site("not a url") is None
    assert showcase_url_for_site("") is None
