# Feature to check new sites on SveltiaCMS showcase page

I want to add a button on the Database States page. It would go on the right side of the Database Stats heading, right-justified. When the button is clicked, the app should go to the following site, fetching the HTML contents:

https://sveltiacms.app/en/showcase?framework=eleventy

This particular page has is a showcase of sites built with Eleventy that use the SveltiaCMS CMS. The app should parse the HTML and extract the list of sites, which includes the site title, description, and URL. That list of sites should be filtered by examining the URL for each site and if the site is already included in the showcase-data.json file, it should be excluded from the list.

The resulting list should be displayed in a modal, with the title as link text to each site's URL. To the left of each site listed, there should be a checkbox. And the modal should have two buttons: (1) Cancel, which exits this feature as if it never happened, and (2) Save Sites, which creates a json file named sveltiacms-sites.json, with each of the "checked" sites being saved to the file.

The json file should have the following format:

```json
[
  {
    "title": "site title",
    "url": "site URL",
    "description": "site description"
  }
]
```

Also add another button to the Database Stats page, which only appears if there are no entries in the sveltiacms-sites.json file. This button should be labeled "Add Next Site to Bundle". When clicked, it should a transition to the Editor page and pre-populate the Create radio button and the Site radio button along with the title and url of the first site in the sveltiacms-sites.json file. The user can then edit the title and url as needed, and then click through the rest of the steps to add the site to the bundle. Once the site is saved to the bundle, it should be removed from the sveltiacms-sites.json file. If the entry is cancelled in any way, the site should not be removed from the file.
