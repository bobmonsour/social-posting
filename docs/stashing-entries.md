# I need a way to stash entries temprarily

I need a way, when creating a new entry of any type to be able to enter a title and a link and tell the editor to put it aside for later further processing/entering.

What I imagine is that when in the editor and I have selected Create and selected a type, there is also a checkbox to the right of the 4 types that is labeled "Stash It". If I check that box, then when I click the Create button, instead of creating the entry, it will be stashed in a list of stashed entries, storing the title, the link, and the type of entry in a file named stashed-entries.json.

I want to rename the Create Entry and Edit Entry to just Create and Edit.

I would then want a button that is only present when there are 1 or more stashed entries in the file. The button would be labeled "Process Stash" and it would appear to the right of the "Stash It" button. It would also show, in parens, the number of stashed entries. When I click the Process Stash, it would pre-populate the type, title, and link fields with the first stashed entry. I would then be able to edit the type, title, and link as needed and continue to fill out the other fields as in a typical entry. If, for some reason, I click Cancel, the entry remains stashed. If I Save it in any form, it is removed from the stashed entries file and added to the appropriate entries file as a normal entry.
