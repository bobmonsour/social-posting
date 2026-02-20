MODES = {
    "11ty": {
        "label": "11ty",
        "platforms": ["mastodon", "bluesky"],
        "suffixes": {
            "mastodon": "\n\n#11ty @11ty@neighborhood.11ty.dev",
            "bluesky": "\n\n@11ty.dev",
        },
    },
    "11ty-bwe": {
        "label": "11ty BWE",
        "platforms": ["mastodon", "bluesky"],
        "prefixes": {
            "mastodon": "Built with Eleventy: ",
            "bluesky": "Built with Eleventy: ",
            "discord": "Built with Eleventy: ",
        },
        "suffixes": {
            "mastodon": "\n\n#11ty @11ty@neighborhood.11ty.dev",
            "bluesky": "\n\n@11ty.dev",
        },
    },
}


def all_modes():
    """Return the full modes dict for template consumption."""
    return MODES


def get_mode(name):
    """Return a single mode config by name, or None."""
    return MODES.get(name)
