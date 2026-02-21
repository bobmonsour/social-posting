# A Database Management Page

This document outlines the design of a page in the app that provides functionality for managing the bundledb. and showcase-data.json files.

## Getting to the Page

On the Editor page, I want to have a button to the right of the DEPLOY button, naming it DB MGMT. This button will take the user to the Database Management page.

## Functionality of the Page

This page will provide some basic information about the bundledb. and showcase-data.json files. Here are some of the statistical information that I want to display for each of the two files:

### bundledb.json

The following statistics will be displayed for the bundledb.json file:
- Total number of entries
- Number of blog posts
- Number of sites
- Number of releases
- Number of starters
- Number of unique authors
- Number of unique categories

### showcase-data.json

The following statistics will be displayed for the showcase-data.json file:
- Number of showcase entries

### backup file maintenance

Each of the two json files maintains backups in the following locations:

- bundledb.json: `/Users/Bob/Dropbox/Docs/Sites/11tybundle/bundledb-backups/`
- showcase-data.json: `/Users/Bob/Dropbox/Docs/Sites/11tybundle/showcase-data-backups/`

This section of the page will display the number of backup files for each of the two json files, ordered by the month and year of the file date , and provide a button to delete all backup files prior to a selected date for each of the two json files. This will help the user manage the backup files which can accumulate over time.

In addition, for the most recent 10 git commits of the bundledb.json and showcase-data.json files, I want to display the date and time of each commit, a link to the commit on GitHub, followed for each, a list of the entry titles included in the commit. There should be separate lists for the bundledb.json and showcase-data.json commits, even though they are often committed together.

#### Answers to questions

1. My paths to the backup files were slightly incorrect. I have updated the paths here. Yes, there is a separate backup folder for the showcase-data.json file, and the path is now included in the document. I have a question, when are bundledb.json backups created? showcase-data.json files should also be backed up in a parallel manner, depending on the type of data entered. Please expand on how this works now and how we can best include backing up the showcase-data.json file in a way that is consistent with the bundledb.json file.
2. Only show the added entries in the commit.
3. I have rethought the approach to this. The most recent 25 backup files should be retained. That is, whenever a new backup file, of either one, the oldest backup file will be deleted if there are already 25 backup files. This way, the user will always have access to the most recent 25 backup files, and they won't have to worry about manually deleting old backup files. The page will display the number of backup files for each of the two json files, and the date of the oldest backup file that is currently retained.
