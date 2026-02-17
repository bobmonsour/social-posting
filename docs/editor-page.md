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

### An enhancement to the edit feature to fill in missing data

For blog post entries, in the case where any one of the following properties is missing and it gets added when editing a blog post, and there are other blog posts by the same author, the editor should prompt the user, asking if the other blog posts by the same author should be updated with the same value for that property.

These properties are:
- authorSiteDescription
- rssLink
- favicon
- any one of the various socialLinks

### Creating new entries feature

On the editor page, above the "Type" area with radio buttons, add two mode buttons:

- Edit, then treats the type selection as the app currently operates, providing search and edit functionality.
- Create, then treats the type selection as a way to select the type of item to create, and instead of showing search results, it shows an empty form with input fields corresponding to the properties of the selected type. The user can fill in the input fields and save the new item to the bundledb.json file, or cancel the creation of the new item. If a new "site" item is created, an entry should be placed in the built-with-eleventy.md file in markdown link format, with the Title of the new site as the link text and the URL of the new site as the link URL.

In addition, when in Edit mode, there should also be a checkbox to provide the addition of a "Skip" property. If the Skip property is true on the item being edited, it should be checked. If it is not true and the user checks the Skip checkbox, then the Skip property should be added to the item with a value of true. If the Skip property is already true and the user unchecks the Skip checkbox, then the Skip property should be removed from the item. The Skip property is used to indicate that an item should be skipped when generating the website, allowing for temporary removal of items without deleting them from the bundledb.json file.

#### Answers to questions about the create new entries feature

1. New items should be placed at the end of bundledb.json.
2. Type should be prefilled. Date should be set to today's date in yyyy-mm-dd format, but then output in the form of other entries in the file. Issue should be auto-calculated as the next issue number that is already used in the app.
3. Author-field propagation should occur when the same author has existing entries in the file; automatically filling things like favicon, authorSiteDescription, rssLink, and socialLinks based on the most recent entry by that author. This would speed up the creation of new entries for authors who already have entries in the file.

There is one other wrinkle in the process. When creating a new "site" entry, if the user fills in the URL of the site, the editor should attempt to fetch the site's favicon and add it to the new entry. In addition, assuming that the app can make use of the puppeteer library, the editor shoudl attempt to generate a screenshot of the site. Refer to the make-bundle-entries.js file for how this is done. It also results in adding an entry, at the start of the file, to the showcase-data.json file located as a peer file to the bundledb.json file. See that file for the format of entries. And if possible, show a preview of the screenshot in the editor page after it is captured.

#### More answers to questions about the create new entries feature

1. Use the Puppeteer (Node) library for screenshot capture.
2. The getfavicon.js uses multiple techniques to find the favicon, beyond just the Google API. I would like this enhanced search technique to be used in the editor page as well, to increase the chances of successfully finding a favicon for new entries.
