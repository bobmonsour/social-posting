# Committing and pushing the db files on deploy

When using the Deploy feature, once a deployment is successful, the db files are not automatically committed and pushed to the repository. To ensure that the db files are included in the repository, do the following steps. First, the location of the db files is:

/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb

The two files that may have changed upon a successful deployment are:

- bundledb.json
- showcase-data.json

Commits and pushes to the current project will be handled separately, but it would be good if these were committed automatically upon completion of a successful deployment.
