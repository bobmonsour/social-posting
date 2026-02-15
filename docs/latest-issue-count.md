# Adding latest issue counts to the social posting app

This document describes how to add the latest issue counts to the social posting app.

## Getting the latest issue counts

There is a script in the following directory named get-issue.counts.js

/Users/Bob/Dropbox/Docs/Sites/11tybundle/dbtools

When run from the command line, it prompts the user for an issue number and then retrieves the latest issue counts from the database. Specifically, it lists the number of each type of item, i.e., blog posts, sites, releases, and starters, from the 11tybundledb.json file that have that issue number as the value of the Issue property..

The 11tybundledb.json file is located in the following directory:

/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb

## Integrating the issue counts into the social posting app

First, I would like for the interface of the app to be a little wider. This is a local-use only app and I am working on a relatively large screen.

What I would like to see is the following displayed above the "Recent Posts" section:

Latest Issue: nn, where nn is the highest issue number in the database. The words "Latest Issue:" and the issue number should be in the same form as the "Recent Posts" heading.

Below that, I would like to see the following, in a smaller font size:

Blog Posts: nn Site: nn Releases: nn Starters: nn

Where the "nn" values are the counts of each type of item for the latest issue number. The words "Blog Posts:", "Site:", "Releases:", and "Starters:" should be in the same form as the "Recent Posts" heading, but in a smaller font size. The counts should be in a different color than the text, and also in a smaller font size than the text.
