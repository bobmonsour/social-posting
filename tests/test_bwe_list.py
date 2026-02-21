import services.bwe_list as bwe_list


def test_parse_bwe_file_well_formed(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 2
    assert to_post[0]["name"] == "My Cool Site"
    assert to_post[0]["url"] == "https://mycoolsite.dev"
    assert to_post[1]["name"] == "Another Site"
    assert len(posted) == 1
    assert posted[0]["name"] == "Posted Site"
    assert posted[0]["date"] == "2026-01-10"
    assert posted[0]["status"] == "Posted to Mastodon"


def test_parse_bwe_file_empty(tmp_path, monkeypatch):
    path = tmp_path / "empty.md"
    path.write_text("")
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))
    to_post, posted = bwe_list.parse_bwe_file()
    assert to_post == []
    assert posted == []


def test_parse_bwe_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(tmp_path / "nonexistent.md"))
    to_post, posted = bwe_list.parse_bwe_file()
    assert to_post == []
    assert posted == []


def test_add_bwe_to_post(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    bwe_list.add_bwe_to_post("New Site", "https://newsite.dev")
    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 3
    assert to_post[2]["name"] == "New Site"
    assert to_post[2]["url"] == "https://newsite.dev"
    # Posted section unchanged
    assert len(posted) == 1


def test_delete_bwe_to_post(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    bwe_list.delete_bwe_to_post("My Cool Site", "https://mycoolsite.dev")
    to_post, _ = bwe_list.parse_bwe_file()
    assert len(to_post) == 1
    assert to_post[0]["name"] == "Another Site"


def test_delete_bwe_to_post_not_found(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    bwe_list.delete_bwe_to_post("Nonexistent", "https://nope.dev")
    to_post, _ = bwe_list.parse_bwe_file()
    assert len(to_post) == 2  # unchanged


def test_delete_bwe_posted(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    bwe_list.delete_bwe_posted("Posted Site", "https://posted.dev")
    _, posted = bwe_list.parse_bwe_file()
    assert len(posted) == 0


def test_mark_bwe_posted(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    bwe_list.mark_bwe_posted(
        "My Cool Site", "https://mycoolsite.dev",
        "2026-02-15T12:00:00+00:00", "Posted to Mastodon, Posted to Bluesky"
    )
    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 1  # removed from to_post
    assert to_post[0]["name"] == "Another Site"
    assert len(posted) == 2  # added to front of posted
    assert posted[0]["name"] == "My Cool Site"
    assert posted[0]["date"] == "2026-02-15"
    assert posted[0]["status"] == "Posted to Mastodon, Posted to Bluesky"


def test_parse_posted_without_status(tmp_path, monkeypatch):
    content = (
        "- TO BE POSTED -\n\n"
        "- ALREADY POSTED -\n"
        "2026-01-01 [No Status Site](https://nostatus.dev)\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))
    _, posted = bwe_list.parse_bwe_file()
    assert len(posted) == 1
    assert posted[0]["status"] == ""
