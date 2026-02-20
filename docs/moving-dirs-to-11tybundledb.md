# Moving favicons and screenshots to 11tybundledb

This document describes how to move the favicons and screenshots directories to 11tybundledb.

## Making and editing entries

When entries are created where favicons are fetched and screenshots are generated, the current process is to store them in the `favicons` and `screenshots` directories respectively, of both the dbtools directory and the 11tybundle.dev directory.

## Relocaing those directories from dbtools

The favicons and screenshots which are currently stored in the dbtools directory should now be stored in the favicons and screenshots directories of the 11tybundledb directory. The app must be updated to support this.

Note that favicons and screenshots should still be stored in the 11tybundle.dev directory, as they are used by the 11tybundledb app.
