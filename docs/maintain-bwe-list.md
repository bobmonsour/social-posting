# Maintaining and posting from a "built with eleventy" list

This page described a feature that I want to add to the social-posting app. It involves examining a markdown file that contains a list of sites built with eleventy, and then posting one of them each day. Details described below.

## A markdown file of sites built with eleventy

A markdown file exists at the root of this repository called `built-with-eleventy.md`. It contains a list of sites built with eleventy. The file is in two sections.

The first section is the list that have not yet been posted to Mastodon and Bluesky. The first section will take the following form, with a header for the section and then a list of items in the format of a markdown link:

- TO BE POSTED -
[Site Name](https://siteurl.com)

Once a site has been posted to Mastodon and Bluesky, it will be moved to the second section of the file. The second section is the list of sites that have already been posted. This second section will take the following form, with a header for the section and then a list of items in the format shown below.

- ALREADY POSTED -
<timestamp with date and time of posting> - [Site Name](https://siteurl.com)

An item will be moved from the first section to the second section once it has been posted to both Mastodon and Bluesky. The timestamp will be the date and time that the item was posted to Mastodon as recorded by the app.

## Upon app launch (or reload)

When the app is started either from initial launch or a reload of the site, it should do the following:

- Read the `built-with-eleventy.md` file and parse the list of sites that are in the "TO BE POSTED" section.
- If there are any sites in the "TO BE POSTED" section, it should select the first item in the list and pre-populate the posting form as follows:

- check both boxes for Mastodon and Bluesky
- check the "11ty BWE" box
- the text area of both social media platforms should be populated as they usually are when the "11ty BWE" box is checked, but with the Site Name following the "Built with Eleventy:" text.
- the url for the site should be placed in the URL field of the form.

## One post per day

If a site has already been posted to Mastodon and Bluesky, the app should not post another site until 24 hours have passed since the last posting. This means that if there are multiple sites in the "TO BE POSTED" section, they will be posted one at a time, with at least 24 hours between each posting. This determination is made each time the app is launched or reloaded.

### Answers to questions

1. Please create an initial built-with-eleventy.md file with an example.
2. Allow editing of the form.
3. If at least one of the platform posts has succeeded, the item should be moved to the "Already Posted" section. In addition, a note for which platforms succeeded shshould be appended to the end of the line for that item in the "Already Posted" section. For example, if the post to Mastodon succeeded but the post to Bluesky failed, the line for that item in the "Already Posted" section would look like this:
<timestamp with date and time of posting> - [Site Name](https://siteurl.com) - Posted to Mastodon, Failed to post to Bluesky
4. A small banner indicating as you suggest would be nice.

## Adding the list of "built with eleventy" sites to the app

I want to add the list of the "- TO BE POSTED -" section of the `built-with-eleventy.md` file to the app. There should be a section below the list of "Recent Posts". In the case where the list is empty, it should say "No sites to post". Next to the title of this new section, which should be called "Sites to Post", there should be a parenthetical that has the number of items in the to be posted list. For example, if there are 3 items in the list, the title of the section would be "Sites to Post (3)". After posting one of these items, the list should be shown updated.

## Duplication of BWE entries

Here is the sequence that results in duplicate drafts in the Recent Posts section of the app.

1. Click on small POST button in the "Sites to Post" section.
2. Save it as a draft. It appears in the Recent Posts section of the app as a draft.
3. Small POST button becomes a small USE button in the "Sites to Post" section.
4. Click on the USE button in the "Sites to Post" section.
5. Save it as a draft.
6. The small POST button re-appears in the "Sites to Post" section.
7. Save it as a draft, which results in a duplicate draft in the Recent Posts section.
