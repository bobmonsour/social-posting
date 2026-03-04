# Checking for favicons and screenshots before building

I move from my desktop to my laptop when I am traveling. And though I have Dropbox set up to sync files, that syncing is not great when referencing favicon files and screenshot files for the 11tybundle.dev site build.

What I need to have happen whenever I click Save or Save and Run Latest is the following:

- do a git -A add to stage all the files in the 11tybundledb repo; which include the favicons and screenshots for the new entry
- push those changes to Github
- loop over the blog post, site, and starter entries that are in the latest issue and check for the presence of the favicon and screenshot files for each of those entries; the favicons need to be present in the 11tybundle.dev/_site/img/favicons directory and the screenshots need to be present in the 11tybundle.dev/content/screenshots directory
- if any of those files are missing, they need to be copied from the 11tybundledb repo; with favicons coming from the favicons directory and being copied to the 11tybundle.dev/_site/img/favicons directory and screenshots coming from the screenshots directory and being copied to the 11tybundle.dev/content/screenshots directory
