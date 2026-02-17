(function () {
  "use strict";

  let allData = [];
  let fuse = null;
  let currentType = null;
  let currentIndex = null; // index into allData (null = create mode)
  let currentMode = "edit"; // "edit" or "create"
  let backupCreated = false;
  let originalItem = null; // snapshot before editing
  let uniqueAuthors = []; // for autocomplete
  let uniqueCategories = []; // for checkbox list

  // Fields eligible for author-level propagation (empty→non-empty triggers prompt)
  const PROPAGATABLE_FIELDS = ["AuthorSiteDescription", "rssLink", "favicon"];
  const PROPAGATABLE_SOCIAL = ["mastodon", "bluesky", "youtube", "github", "linkedin"];

  // Field order per type
  const FIELD_ORDER = {
    "blog post": [
      "Issue", "Type", "Title", "slugifiedTitle", "Link", "Date",
      "formattedDate", "description", "Author", "slugifiedAuthor",
      "AuthorSite", "AuthorSiteDescription", "socialLinks", "favicon",
      "rssLink", "Categories"
    ],
    site: [
      "Issue", "Type", "Title", "description", "Link", "Date",
      "formattedDate", "favicon", "screenshotpath"
    ],
    release: [
      "Issue", "Type", "Title", "description", "Link", "Date",
      "formattedDate"
    ],
    starter: [
      "Issue", "Type", "Title", "Link", "Demo", "description",
      "screenshotpath"
    ]
  };

  const SOCIAL_LINK_FIELDS = ["mastodon", "bluesky", "youtube", "github", "linkedin"];

  const SEARCH_KEYS = {
    "blog post": ["Title", "Author"],
    site: ["Title"],
    release: ["Title"],
    starter: ["Title"]
  };

  // DOM refs
  const modeRadios = document.querySelectorAll('input[name="editor-mode"]');
  const typeRadios = document.querySelectorAll('input[name="item-type"]');
  const searchSection = document.getElementById("search-section");
  const searchInput = document.getElementById("search-input");
  const recentItems = document.getElementById("recent-items");
  const recentItemsList = document.getElementById("recent-items-list");
  const searchResults = document.getElementById("search-results");
  const searchResultsList = document.getElementById("search-results-list");
  const editFormContainer = document.getElementById("edit-form-container");
  const editFormTitle = document.getElementById("edit-form-title");
  const editFormFields = document.getElementById("edit-form-fields");
  const btnSave = document.getElementById("btn-save");
  const btnCancel = document.getElementById("btn-cancel");
  const statusMessage = document.getElementById("status-message");

  // Load data on page load
  fetch("/editor/data")
    .then((r) => r.json())
    .then((data) => {
      allData = data;
      buildUniqueAuthors();
      buildUniqueCategories();
    })
    .catch((err) => {
      showStatus("Failed to load data: " + err.message, true);
    });

  function buildUniqueAuthors() {
    const authors = new Set();
    for (let i = 0; i < allData.length; i++) {
      if (allData[i].Type === "blog post" && allData[i].Author) {
        authors.add(allData[i].Author);
      }
    }
    uniqueAuthors = Array.from(authors).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base" })
    );
  }

  function buildUniqueCategories() {
    const cats = new Set();
    for (let i = 0; i < allData.length; i++) {
      const c = allData[i].Categories;
      if (Array.isArray(c)) {
        c.forEach((cat) => { if (cat) cats.add(cat); });
      }
    }
    uniqueCategories = Array.from(cats).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base" })
    );
  }

  // Mode change handler
  modeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      currentMode = radio.value;
      hideEditForm();
      searchInput.value = "";
      searchResults.style.display = "none";
      recentItems.style.display = "none";

      if (currentMode === "edit") {
        searchSection.style.display = currentType ? "" : "none";
        if (currentType) {
          showRecentItems();
          initFuse();
        }
      } else {
        // Create mode: hide search, show create form if type selected
        searchSection.style.display = "none";
        if (currentType) {
          showCreateForm();
        }
      }
    });
  });

  // Type change handler
  typeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      currentType = radio.value;
      searchInput.value = "";
      hideEditForm();

      if (currentMode === "edit") {
        searchSection.style.display = "";
        showRecentItems();
        searchResults.style.display = "none";
        initFuse();
        searchInput.focus();
      } else {
        searchSection.style.display = "none";
        recentItems.style.display = "none";
        searchResults.style.display = "none";
        showCreateForm();
      }
    });
  });

  // Search input handler
  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const query = searchInput.value.trim();
      if (!query) {
        searchResults.style.display = "none";
        recentItems.style.display = "";
        showRecentItems();
        return;
      }
      recentItems.style.display = "none";
      runSearch(query);
    }, 200);
  });

  // Save handler
  btnSave.addEventListener("click", saveItem);

  // Cancel handler
  btnCancel.addEventListener("click", () => {
    hideEditForm();
    if (currentMode === "edit") {
      if (searchInput.value.trim()) {
        runSearch(searchInput.value.trim());
      } else {
        showRecentItems();
      }
    }
  });

  function getItemsOfType(type) {
    const items = [];
    for (let i = 0; i < allData.length; i++) {
      if (allData[i].Type === type) {
        items.push({ item: allData[i], index: i });
      }
    }
    return items;
  }

  function showRecentItems() {
    if (!currentType) return;
    const typed = getItemsOfType(currentType);
    // Sort by Date descending
    typed.sort((a, b) => (b.item.Date || "").localeCompare(a.item.Date || ""));
    const recent = typed.slice(0, 5);
    recentItemsList.innerHTML = "";
    recent.forEach(({ item, index }) => {
      recentItemsList.appendChild(createItemCard(item, index));
    });
    recentItems.style.display = "";
  }

  function initFuse() {
    if (!currentType) return;
    const typed = getItemsOfType(currentType);
    const keys = SEARCH_KEYS[currentType] || ["Title"];
    fuse = new Fuse(typed, {
      keys: keys.map((k) => "item." + k),
      threshold: 0.4,
      includeScore: true
    });
  }

  function runSearch(query) {
    if (!fuse) return;
    const results = fuse.search(query, { limit: 20 });
    searchResultsList.innerHTML = "";
    if (results.length === 0) {
      searchResultsList.innerHTML = '<p class="muted">No results found.</p>';
    } else {
      results.forEach((r) => {
        const { item, index } = r.item;
        searchResultsList.appendChild(createItemCard(item, index));
      });
    }
    searchResults.style.display = "";
  }

  function createItemCard(item, index) {
    const card = document.createElement("div");
    card.className = "item-card";
    card.dataset.index = index;

    let subtitle = "";
    if (item.Author) subtitle = item.Author + " \u00B7 ";
    if (item.formattedDate) subtitle += item.formattedDate;
    else if (item.Date) subtitle += item.Date.slice(0, 10);

    card.innerHTML =
      '<div class="item-card-title">' + escapeHtml(item.Title || "(no title)") + "</div>" +
      (subtitle ? '<div class="item-card-subtitle">' + escapeHtml(subtitle) + "</div>" : "");

    card.addEventListener("click", () => {
      showEditForm(item, index);
    });
    return card;
  }

  // --- Create mode ---

  function getMaxIssue() {
    let max = 0;
    for (let i = 0; i < allData.length; i++) {
      const n = parseInt(allData[i].Issue, 10);
      if (n > max) max = n;
    }
    return max;
  }

  function formatDate(d) {
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return months[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
  }

  function isoDate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()) + ".000";
  }

  function showCreateForm() {
    if (!currentType) return;

    const now = new Date();
    const item = {
      Type: currentType,
      Date: isoDate(now),
      formattedDate: formatDate(now),
      Issue: String(getMaxIssue())
    };

    // Type-specific defaults
    if (currentType === "blog post") {
      item.Title = "";
      item.slugifiedTitle = "";
      item.Link = "";
      item.description = "";
      item.Author = "";
      item.slugifiedAuthor = "";
      item.AuthorSite = "";
      item.AuthorSiteDescription = "";
      item.socialLinks = {};
      item.favicon = "";
      item.rssLink = "";
      item.Categories = [];
    } else if (currentType === "site") {
      item.Title = "";
      item.description = "";
      item.Link = "";
      item.favicon = "";
      item.screenshotpath = "";
    } else if (currentType === "release") {
      item.Title = "";
      item.description = "";
      item.Link = "";
    } else if (currentType === "starter") {
      item.Title = "";
      item.Link = "";
      item.Demo = "";
      item.description = "";
      item.screenshotpath = "";
    }

    currentIndex = null;
    originalItem = null;
    showEditForm(item, null);
  }

  // --- Edit form ---

  function showEditForm(item, index) {
    currentIndex = index;
    if (index !== null) {
      originalItem = JSON.parse(JSON.stringify(item));
    }
    const fields = FIELD_ORDER[currentType] || Object.keys(item);
    const isCreate = index === null;

    editFormTitle.textContent = (isCreate ? "Create: " : "Edit: ") +
      (currentType.charAt(0).toUpperCase() + currentType.slice(1));
    if (!isCreate && item.Title) {
      editFormTitle.textContent = "Edit: " + item.Title;
    }
    editFormFields.innerHTML = "";

    // Hide search/recent
    recentItems.style.display = "none";
    searchResults.style.display = "none";

    // Skip checkbox (edit mode only)
    if (!isCreate) {
      const skipRow = document.createElement("div");
      skipRow.className = "form-field-skip";
      const skipCb = document.createElement("input");
      skipCb.type = "checkbox";
      skipCb.id = "field-Skip";
      skipCb.checked = item.Skip === true;
      const skipLabel = document.createElement("label");
      skipLabel.textContent = "Skip (exclude from site generation)";
      skipLabel.setAttribute("for", "field-Skip");
      skipRow.appendChild(skipCb);
      skipRow.appendChild(skipLabel);
      editFormFields.appendChild(skipRow);
    }

    fields.forEach((field) => {
      if (field === "socialLinks") {
        renderSocialLinksFieldset(item);
      } else if (field === "Categories") {
        renderCategoriesField(item);
      } else if (field === "description") {
        renderDescriptionField(item);
      } else if (field === "Author" && isCreate && currentType === "blog post") {
        renderAuthorFieldWithAutocomplete(item);
      } else {
        renderTextField(field, item);
      }

      // Insert fetch button after Link field for site creates
      if (field === "Link" && isCreate && currentType === "site") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-action btn-fetch-data";
        btn.textContent = "Fetch Favicon & Screenshot";
        btn.addEventListener("click", fetchSiteData);
        editFormFields.appendChild(btn);
      }
    });

    editFormContainer.style.display = "";
    editFormContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderSocialLinksFieldset(item) {
    const fs = document.createElement("fieldset");
    fs.className = "nested-fieldset";
    const legend = document.createElement("legend");
    legend.textContent = "Social Links";
    fs.appendChild(legend);

    const links = item.socialLinks || {};
    SOCIAL_LINK_FIELDS.forEach((key) => {
      const row = document.createElement("div");
      row.className = "form-field";
      const label = document.createElement("label");
      label.textContent = key;
      label.setAttribute("for", "field-sl-" + key);
      const input = document.createElement("input");
      input.type = "text";
      input.id = "field-sl-" + key;
      input.name = "socialLinks." + key;
      input.value = links[key] || "";
      row.appendChild(label);
      row.appendChild(input);
      fs.appendChild(row);
    });
    editFormFields.appendChild(fs);
  }

  function renderCategoriesField(item) {
    const fs = document.createElement("fieldset");
    fs.className = "nested-fieldset categories-fieldset";
    const legend = document.createElement("legend");
    legend.textContent = "Categories";
    fs.appendChild(legend);

    const selected = new Set(
      Array.isArray(item.Categories) ? item.Categories : []
    );

    const grid = document.createElement("div");
    grid.className = "categories-grid";

    uniqueCategories.forEach((cat) => {
      const lbl = document.createElement("label");
      lbl.className = "category-checkbox";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.name = "cat-checkbox";
      cb.value = cat;
      cb.checked = selected.has(cat);
      lbl.appendChild(cb);
      lbl.appendChild(document.createTextNode(" " + cat));
      grid.appendChild(lbl);
    });

    fs.appendChild(grid);

    // Add new category input
    const addRow = document.createElement("div");
    addRow.className = "category-add-row";
    const addInput = document.createElement("input");
    addInput.type = "text";
    addInput.id = "field-new-category";
    addInput.placeholder = "Add new category...";
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn-action btn-secondary";
    addBtn.textContent = "Add";
    addBtn.addEventListener("click", () => {
      const val = addInput.value.trim();
      if (!val) return;
      // Avoid duplicates
      const existing = grid.querySelector(
        'input[value="' + CSS.escape(val) + '"]'
      );
      if (existing) {
        existing.checked = true;
        addInput.value = "";
        return;
      }
      // Add checkbox
      const lbl = document.createElement("label");
      lbl.className = "category-checkbox";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.name = "cat-checkbox";
      cb.value = val;
      cb.checked = true;
      lbl.appendChild(cb);
      lbl.appendChild(document.createTextNode(" " + val));
      grid.appendChild(lbl);
      addInput.value = "";
    });
    addRow.appendChild(addInput);
    addRow.appendChild(addBtn);
    fs.appendChild(addRow);

    editFormFields.appendChild(fs);
  }

  function renderDescriptionField(item) {
    const row = document.createElement("div");
    row.className = "form-field";
    const label = document.createElement("label");
    label.textContent = "description";
    label.setAttribute("for", "field-description");
    const textarea = document.createElement("textarea");
    textarea.id = "field-description";
    textarea.name = "description";
    textarea.rows = 3;
    textarea.value = item.description || "";
    row.appendChild(label);
    row.appendChild(textarea);
    editFormFields.appendChild(row);
  }

  function renderAuthorFieldWithAutocomplete(item) {
    const row = document.createElement("div");
    row.className = "form-field";
    const label = document.createElement("label");
    label.textContent = "Author";
    label.setAttribute("for", "field-Author");
    const input = document.createElement("input");
    input.type = "text";
    input.id = "field-Author";
    input.name = "Author";
    input.value = item.Author || "";
    input.setAttribute("list", "author-datalist");
    input.setAttribute("autocomplete", "off");

    // Build datalist
    const datalist = document.createElement("datalist");
    datalist.id = "author-datalist";
    uniqueAuthors.forEach((author) => {
      const opt = document.createElement("option");
      opt.value = author;
      datalist.appendChild(opt);
    });

    // Tab to complete: if input narrows to a single match, fill it
    input.addEventListener("keydown", (e) => {
      if (e.key !== "Tab") return;
      const typed = input.value.trim().toLowerCase();
      if (!typed) return;
      const matches = uniqueAuthors.filter((a) =>
        a.toLowerCase().includes(typed)
      );
      if (matches.length === 1 && matches[0] !== input.value) {
        input.value = matches[0];
        autoFillFromAuthor(matches[0]);
      }
    });

    // Auto-fill on selection
    input.addEventListener("change", () => {
      autoFillFromAuthor(input.value.trim());
    });

    row.appendChild(label);
    row.appendChild(input);
    row.appendChild(datalist);
    editFormFields.appendChild(row);
  }

  function autoFillFromAuthor(name) {
    if (!name || !uniqueAuthors.includes(name)) return;

    // Find most recent blog post by this author
    let best = null;
    for (let i = 0; i < allData.length; i++) {
      if (allData[i].Type === "blog post" && allData[i].Author === name) {
        if (!best || (allData[i].Date || "") > (best.Date || "")) {
          best = allData[i];
        }
      }
    }
    if (!best) return;

    // Auto-fill empty fields
    const fillMap = {
      "AuthorSite": best.AuthorSite,
      "AuthorSiteDescription": best.AuthorSiteDescription,
      "favicon": best.favicon,
      "rssLink": best.rssLink,
      "slugifiedAuthor": best.slugifiedAuthor
    };

    for (const [field, value] of Object.entries(fillMap)) {
      if (!value) continue;
      const el = document.getElementById("field-" + field);
      if (el && !el.value.trim()) {
        el.value = value;
      }
    }

    // Auto-fill social links
    if (best.socialLinks) {
      SOCIAL_LINK_FIELDS.forEach((key) => {
        const val = best.socialLinks[key];
        if (!val) return;
        const el = document.getElementById("field-sl-" + key);
        if (el && !el.value.trim()) {
          el.value = val;
        }
      });
    }
  }

  function fieldLabel(field) {
    if (field === "Link" && (currentType === "release" || currentType === "starter")) {
      return "GitHub repo link";
    }
    if (field === "Demo" && currentType === "starter") {
      return "Link to demo site";
    }
    return field;
  }

  function renderTextField(field, item) {
    const row = document.createElement("div");
    row.className = "form-field";
    const label = document.createElement("label");
    label.textContent = fieldLabel(field);
    label.setAttribute("for", "field-" + field);
    const input = document.createElement("input");
    input.type = "text";
    input.id = "field-" + field;
    input.name = field;
    input.value = item[field] != null ? String(item[field]) : "";
    row.appendChild(label);
    row.appendChild(input);
    editFormFields.appendChild(row);
  }

  function hideEditForm() {
    editFormContainer.style.display = "none";
    currentIndex = null;
    // Remove any screenshot preview
    const preview = document.querySelector(".screenshot-preview");
    if (preview) preview.remove();
  }

  function collectFormValues() {
    const item = {};
    const fields = FIELD_ORDER[currentType] || [];

    fields.forEach((field) => {
      if (field === "socialLinks") {
        const links = {};
        SOCIAL_LINK_FIELDS.forEach((key) => {
          const input = document.querySelector('[name="socialLinks.' + key + '"]');
          links[key] = input ? input.value : "";
        });
        item.socialLinks = links;
      } else if (field === "Categories") {
        const checked = document.querySelectorAll('input[name="cat-checkbox"]:checked');
        item.Categories = Array.from(checked).map((cb) => cb.value);
      } else {
        const el = document.getElementById("field-" + field);
        item[field] = el ? el.value : "";
      }
    });

    // Skip checkbox (only in edit mode)
    if (currentIndex !== null) {
      const skipCb = document.getElementById("field-Skip");
      if (skipCb && skipCb.checked) {
        item.Skip = true;
      }
    }

    return item;
  }

  function buildPropagation(item) {
    // Only for blog posts with an author and a stored original (edit mode)
    if (currentType !== "blog post" || !originalItem || !item.Author) return [];

    // Find fields that went from empty to non-empty
    const newlyFilled = [];
    PROPAGATABLE_FIELDS.forEach((f) => {
      const oldVal = (originalItem[f] || "").trim();
      const newVal = (item[f] || "").trim();
      if (!oldVal && newVal) newlyFilled.push({ field: f, value: newVal });
    });
    const origSocial = originalItem.socialLinks || {};
    const newSocial = item.socialLinks || {};
    PROPAGATABLE_SOCIAL.forEach((key) => {
      const oldVal = (origSocial[key] || "").trim();
      const newVal = (newSocial[key] || "").trim();
      if (!oldVal && newVal) newlyFilled.push({ field: "socialLinks." + key, value: newVal });
    });

    if (newlyFilled.length === 0) return [];

    // Find other blog posts by same author that are missing these fields
    const author = item.Author;
    const propagate = [];
    for (let i = 0; i < allData.length; i++) {
      if (i === currentIndex) continue;
      if (allData[i].Type !== "blog post" || allData[i].Author !== author) continue;
      newlyFilled.forEach(({ field, value }) => {
        let existing;
        if (field.startsWith("socialLinks.")) {
          const sub = field.split(".")[1];
          existing = ((allData[i].socialLinks || {})[sub] || "").trim();
        } else {
          existing = (allData[i][field] || "").trim();
        }
        if (!existing) {
          propagate.push({ index: i, field, value });
        }
      });
    }

    return propagate;
  }

  function describeNewlyFilled(item) {
    const labels = [];
    PROPAGATABLE_FIELDS.forEach((f) => {
      const oldVal = (originalItem[f] || "").trim();
      const newVal = (item[f] || "").trim();
      if (!oldVal && newVal) labels.push(f);
    });
    const origSocial = originalItem.socialLinks || {};
    const newSocial = item.socialLinks || {};
    PROPAGATABLE_SOCIAL.forEach((key) => {
      const oldVal = (origSocial[key] || "").trim();
      const newVal = (newSocial[key] || "").trim();
      if (!oldVal && newVal) labels.push("socialLinks." + key);
    });
    return labels;
  }

  function saveItem() {
    const isCreate = currentIndex === null;

    if (!isCreate && currentIndex === null) return;

    const item = collectFormValues();

    // Check for author-level propagation (edit mode only)
    const propagate = isCreate ? [] : buildPropagation(item);
    let doPropagate = false;
    if (propagate.length > 0) {
      const fields = describeNewlyFilled(item);
      const otherCount = new Set(propagate.map((p) => p.index)).size;
      const msg =
        "You added " + fields.join(", ") + ".\n" +
        otherCount + " other post" + (otherCount === 1 ? "" : "s") +
        " by " + item.Author + " " +
        (otherCount === 1 ? "is" : "are") +
        " missing " + (fields.length === 1 ? "this field" : "some of these fields") +
        ". Update them too?";
      doPropagate = confirm(msg);
    }

    btnSave.disabled = true;
    btnSave.textContent = "Saving...";

    const payload = {
      item: item,
      backup_created: backupCreated
    };

    if (isCreate) {
      payload.create = true;
    } else {
      payload.index = currentIndex;
    }
    if (doPropagate) payload.propagate = propagate;

    fetch("/editor/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          backupCreated = data.backup_created;

          if (isCreate) {
            allData.push(item);
            buildUniqueAuthors();
          } else {
            allData[currentIndex] = item;
            // Sync propagated changes into local allData
            if (doPropagate && propagate.length > 0) {
              propagate.forEach(({ index: idx, field, value }) => {
                if (field.startsWith("socialLinks.")) {
                  const sub = field.split(".")[1];
                  if (!allData[idx].socialLinks) allData[idx].socialLinks = {};
                  allData[idx].socialLinks[sub] = value;
                } else {
                  allData[idx][field] = value;
                }
              });
            }
          }

          hideEditForm();
          initFuse();
          let msg = isCreate ? "Created successfully." : "Saved successfully.";
          const propCount = data.propagated || 0;
          if (propCount > 0) msg += " Updated " + propCount + " other post" + (propCount === 1 ? "" : "s") + ".";
          if (data.bwe_added) msg += " Added to BWE list.";
          if (data.showcase_added) msg += " Added to showcase.";
          showStatus(msg, false);

          // Restore search/recent view (edit mode)
          if (currentMode === "edit") {
            if (searchInput.value.trim()) {
              runSearch(searchInput.value.trim());
            } else {
              showRecentItems();
            }
          }
        } else {
          showStatus("Save failed: " + (data.error || "Unknown error"), true);
        }
      })
      .catch((err) => {
        showStatus("Save failed: " + err.message, true);
      })
      .finally(() => {
        btnSave.disabled = false;
        btnSave.textContent = "Save";
      });
  }

  // --- Site create: fetch favicon & screenshot ---

  function fetchSiteData() {
    const linkEl = document.getElementById("field-Link");
    const url = linkEl ? linkEl.value.trim() : "";
    if (!url) {
      showStatus("Enter a Link first.", true);
      return;
    }

    const btn = editFormFields.querySelector(".btn-fetch-data");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Fetching...";
    }

    // Fetch favicon and screenshot in parallel
    const faviconPromise = fetch("/editor/favicon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    const screenshotPromise = fetch("/editor/screenshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    Promise.all([faviconPromise, screenshotPromise]).then(([favResult, ssResult]) => {
      if (favResult.success && favResult.favicon) {
        const favEl = document.getElementById("field-favicon");
        if (favEl) favEl.value = favResult.favicon;
      }

      if (ssResult.success && ssResult.screenshotpath) {
        const ssEl = document.getElementById("field-screenshotpath");
        if (ssEl) ssEl.value = ssResult.screenshotpath;

        // Show screenshot preview
        if (ssResult.filename) {
          // Remove existing preview
          const existing = document.querySelector(".screenshot-preview");
          if (existing) existing.remove();

          const img = document.createElement("img");
          img.className = "screenshot-preview";
          img.src = "/editor/screenshot-preview/" + ssResult.filename;
          img.alt = "Screenshot preview";
          editFormFields.appendChild(img);
        }
      }

      let msgs = [];
      if (favResult.success) msgs.push("Favicon fetched");
      else msgs.push("Favicon failed");
      if (ssResult.success) msgs.push("Screenshot captured");
      else msgs.push("Screenshot failed");
      showStatus(msgs.join(". ") + ".", !favResult.success && !ssResult.success);
    }).finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Fetch Favicon & Screenshot";
      }
    });
  }

  function showStatus(msg, isError) {
    statusMessage.textContent = msg;
    statusMessage.className = isError ? "status-error" : "status-success";
    statusMessage.style.display = "";
    setTimeout(() => {
      statusMessage.style.display = "none";
    }, 4000);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
