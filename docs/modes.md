# Adding modes of operation to social-posting

This document outlines the different modes of operation for the social-posting application. Specifically, it focuses on having mentions and hashtags that are platform-aware and specifically created and formatted for each platform.

## Modes of Operation

I would like there to be what I will call an "eleventy" mode of operation that is set via a checkbox in the interface. The check box should be named "11ty". If this mode is enabled, then the application should display separate input boxes for each platform (Mastodon and Bluesky) and allow the user to create platform-specific content, including mentions and hashtags that are formatted correctly for each platform. The user should also be able to see a preview of how the post will look on each platform before posting.

## Mastodon-specific features for the "11ty" mode

When the "11ty" mode is enabled, the application should add the following hashtags and mentions in the input box, yet the cursor for user entry shall be at the start of the text box so that the user can start typing immediately without needing to move the cursor:

- Hashtags: #11ty
- Mentions: @11ty@neighborhood.11ty.dev

## Bluesky-specific features for the "11ty" mode

When the "11ty" mode is enabled, the application should add the following mentions in the input box, yet the cursor for user entry shall be at the start of the text box so that the user can start typing immediately without needing to move the cursor:

-Mentions: @11ty.dev

## Answers to the first round of Claude questions

1. It should be near the platform checkboxes
2. When 11ty mode is selected, it shoudl auto-check both Mastodon and Bluesky checkboxes.
3. Previews should be triggered by a button.
4. Drafts can be stored together for both platforms in 11ty mode.
5. There may be more modes in the future.

## An enhancement to 11ty mode

I would like for the text that I enter in either of the platform boxes to be duplicated to the other platform box so that I do not have to type it twice.

## New mode, related to 11ty mode, called "11ty BWE"

The new "11ty BWE" mode behaves similar to the "11ty" mode, but differs in that it adds the following text that immediately precedes the any hashtags and mentions:

"Built with Eleventy"
