import services.bwe_list as bwe_list


def test_parse_bwe_file_well_formed(bwe_file, monkeypatch):
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(bwe_file))
    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 2
    assert to_post[0]["name"] == "My Cool Site"
    assert to_post[0]["url"] == "https://mycoolsite.dev"
    assert to_post[0]["platforms"] == ["B", "M"]  # default platforms
    assert to_post[1]["name"] == "Another Site"
    assert to_post[1]["platforms"] == ["B", "M"]
    assert len(posted) == 1
    assert posted[0]["name"] == "Posted Site"
    assert posted[0]["date"] == "2026-01-10"
    assert posted[0]["status"] == "Posted to Mastodon"
    assert posted[0]["platforms"] == ["M"]  # extracted from legacy status


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
    assert to_post[2]["platforms"] == ["B", "M"]
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
    assert posted[0]["platforms"] == ["B", "M"]


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
    assert posted[0]["platforms"] == []


# --- New per-platform tracking tests ---


def test_parse_to_post_with_platform_specifier(tmp_path, monkeypatch):
    content = (
        "- TO BE POSTED -\n"
        "[Site A](https://a.dev) {D}\n"
        "[Site B](https://b.dev) {M,B,D}\n"
        "[Site C](https://c.dev)\n"
        "\n- ALREADY POSTED -\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))
    to_post, _ = bwe_list.parse_bwe_file()
    assert len(to_post) == 3
    assert to_post[0]["platforms"] == ["D"]
    assert to_post[1]["platforms"] == ["B", "D", "M"]
    assert to_post[2]["platforms"] == ["B", "M"]  # default


def test_parse_posted_with_platform_spec(tmp_path, monkeypatch):
    content = (
        "- TO BE POSTED -\n\n"
        "- ALREADY POSTED -\n"
        "2026-02-20 [Site X](https://x.dev) {M,B}\n"
        "2026-02-19 [Site Y](https://y.dev) {D}\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))
    _, posted = bwe_list.parse_bwe_file()
    assert len(posted) == 2
    assert posted[0]["platforms"] == ["B", "M"]
    assert posted[1]["platforms"] == ["D"]


def test_parse_posted_backward_compat_status(tmp_path, monkeypatch):
    content = (
        "- TO BE POSTED -\n\n"
        "- ALREADY POSTED -\n"
        "2026-01-10 [Old Site](https://old.dev) \u2014 Posted to Mastodon, Posted to Bluesky\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))
    _, posted = bwe_list.parse_bwe_file()
    assert len(posted) == 1
    assert posted[0]["platforms"] == ["B", "M"]
    assert posted[0]["status"] == "Posted to Mastodon, Posted to Bluesky"


def test_update_bwe_after_post_full(tmp_path, monkeypatch):
    """Post to all platforms on an entry — should fully move to posted."""
    content = (
        "- TO BE POSTED -\n"
        "[My Site](https://mysite.dev)\n"
        "\n- ALREADY POSTED -\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))

    bwe_list.update_bwe_after_post("My Site", "https://mysite.dev", ["M", "B"], "2026-02-21T10:00:00Z")

    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 0
    assert len(posted) == 1
    assert posted[0]["name"] == "My Site"
    assert posted[0]["platforms"] == ["B", "M"]


def test_update_bwe_after_post_partial(tmp_path, monkeypatch):
    """Post to only M — site should stay in to_post with B remaining."""
    content = (
        "- TO BE POSTED -\n"
        "[My Site](https://mysite.dev)\n"
        "\n- ALREADY POSTED -\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))

    bwe_list.update_bwe_after_post("My Site", "https://mysite.dev", ["M"], "2026-02-21T10:00:00Z")

    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 1
    assert to_post[0]["name"] == "My Site"
    assert to_post[0]["platforms"] == ["B"]
    assert len(posted) == 1
    assert posted[0]["platforms"] == ["M"]


def test_update_bwe_after_post_merge_existing(tmp_path, monkeypatch):
    """Second partial post should merge with existing posted entry."""
    content = (
        "- TO BE POSTED -\n"
        "[My Site](https://mysite.dev) {B}\n"
        "\n- ALREADY POSTED -\n"
        "2026-02-20 [My Site](https://mysite.dev) {M}\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))

    bwe_list.update_bwe_after_post("My Site", "https://mysite.dev", ["B"], "2026-02-21T10:00:00Z")

    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 0
    assert len(posted) == 1
    assert posted[0]["platforms"] == ["B", "M"]
    assert posted[0]["date"] == "2026-02-21"


def test_default_platform_specifier_omitted_on_write(tmp_path, monkeypatch):
    """Default M,B should not write {M,B} specifier (clean output)."""
    content = (
        "- TO BE POSTED -\n"
        "[Site A](https://a.dev)\n"
        "[Site B](https://b.dev) {D}\n"
        "\n- ALREADY POSTED -\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))

    # Re-parse and write (round-trip)
    to_post, posted = bwe_list.parse_bwe_file()
    bwe_list._write_bwe_file(to_post, posted)

    raw = path.read_text()
    assert "[Site A](https://a.dev)\n" in raw  # no {M,B}
    assert "[Site B](https://b.dev) {D}\n" in raw


def test_update_bwe_after_post_three_platforms(tmp_path, monkeypatch):
    """Post to all three platforms from an entry with M,B,D."""
    content = (
        "- TO BE POSTED -\n"
        "[Site](https://site.dev) {B,D,M}\n"
        "\n- ALREADY POSTED -\n"
    )
    path = tmp_path / "bwe.md"
    path.write_text(content)
    monkeypatch.setattr(bwe_list, "BWE_FILE", str(path))

    bwe_list.update_bwe_after_post("Site", "https://site.dev", ["M", "B", "D"], "2026-02-21T10:00:00Z")

    to_post, posted = bwe_list.parse_bwe_file()
    assert len(to_post) == 0
    assert len(posted) == 1
    assert posted[0]["platforms"] == ["B", "D", "M"]
