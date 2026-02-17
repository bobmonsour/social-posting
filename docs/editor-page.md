# Creating a bundledb.json editor page

This document outlines the features that would be desired in an editor page for bundledb.json files. The editor page should provide a user-friendly interface for managing the contents of bundledb.json, the source database for the 11tybundle.dev website.


## Presenting the editor on its own page of the app

While the main entry point of the app shall still be the "social posting" feature, there should be a new button added next to the page title, i.e., Bob on Social, named "Edit bundledb.json". When clicked, this button should navigate to a new page within the app, dedicated to editing the bundledb.json file. This page should be designed to provide a clear and intuitive interface for managing the contents of the bundledb.json file.

## Presenting the bundledb.json data

The bundledb.json file lives at the following location on this system:

```
/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json
```

The json file contains an array of objects, each representing a bundle item, each of which has a Type property that can be one of the following:

- blog post
- site
- release
- starter

You can examine the file to see what properties each type of item contains.

## Editor page features

### Search

I would like there be a search capability that allows me to quickly find items in the bundledb.json file based on their properties. For example, I should be able to filter the search items by Type. In addition, once a Type is selected, I should be able to search for items of that Type based on their other properties. For example, if I select the Type "blog post", I should be able to search for blog posts by their Title or Author. The interface would show a list of matching items based on the search criteria, displaying the Title of the items matching the search criteria.

The search should be a fuzzy search, not requiring an exact match.

### Edit

An item in the search results should be selectable and when selected, the editor page should display a form with input fields corresponding to the properties of the selected item. The input fields should be pre-populated with the current values of the item's properties. I should be able to edit the values in the input fields and save the changes back to the bundledb.json file, or to cancel the search.
