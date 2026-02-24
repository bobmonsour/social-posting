# Generating an issue of the 11ty bundle blog

This document outlines a new feature, the result of which is to create a new issue of the 11ty bundle blog. This is a manual process, but it is designed to be as simple as possible.

## Interface changes

The interface has to change for this feature. On the social posting page, the New Bundle Issue button should be removed. On the Editor page, a new radio button, titled "Generate Bundle Issue", should be added to the Mode section.

## Action when the Generate Bundle Issue radio button is selected

When the Generate Bundle Issue radio button is selected, similar to Edit Latest Issue presentation, all of the entries for the latest issue should be displayed. However, the items should be narrowed slightly and a checkbox should placed to the left of each item, outside of the bounding box of each item.

The user should be able to select any number of items, and the selected items should be highlighted.

Also, the search label and the search box should be removed and replaced with a large button that says "Generate Bundle Issue". When this button is clicked, the following actions should occur:

- the file in the templates directory of this project, named 11ty-bundle-xx.md should be copied to the /content/blog/yyyy directory of the 11tybundle.dev project. The xx in the filename should be replaced with the next issue number, with the yyyy representing the destination path within the /content/blog directory. For example, if the latest issue is 84 and the current year is 2026, the file should be copied to /content/blog/2026/11ty-bundle-84.md.

- for each of the items with a checked checkbox in the editor interface, an item should be created in the Hightlights section. There are pre-formatted lines in the 11ty-bundle-xx.md file that should be used for this purpose. Following those lines, blog posts which are most often selected for inclusion in the bundle issue should be added so that each "highlights" item takes the following form:

**.** [Author Name](link to the author's website) - [Title of the blog post](link to the blog post)

### Answers to questions

1. For now only blog posts should be selectable.
2. Yes. Removed unused lines.
3. While there are 7 lines for entries in the template, more should be added if more than 7 items are selected for inclusion in the bundle issue.
4. The existing function can be extended for this use as there will not be another way to generate a blog post through the interface.
5. Yes, open the resulting file in VS Code.
