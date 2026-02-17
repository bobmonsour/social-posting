(function () {
  "use strict";

  let allData = [];
  let fuse = null;
  let currentType = null;
  let currentIndex = null; // index into allData
  let backupCreated = false;
  let originalItem = null; // snapshot before editing

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
      "formattedDate", "favicon"
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
    })
    .catch((err) => {
      showStatus("Failed to load data: " + err.message, true);
    });

  // Type change handler
  typeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      currentType = radio.value;
      searchInput.value = "";
      hideEditForm();
      searchSection.style.display = "";
      showRecentItems();
      searchResults.style.display = "none";
      initFuse();
      searchInput.focus();
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
    if (searchInput.value.trim()) {
      runSearch(searchInput.value.trim());
    } else {
      showRecentItems();
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

  function showEditForm(item, index) {
    currentIndex = index;
    originalItem = JSON.parse(JSON.stringify(item));
    const fields = FIELD_ORDER[currentType] || Object.keys(item);

    editFormTitle.textContent = "Edit: " + (item.Title || "(no title)");
    editFormFields.innerHTML = "";

    // Hide search/recent
    recentItems.style.display = "none";
    searchResults.style.display = "none";

    fields.forEach((field) => {
      if (field === "socialLinks") {
        // Nested fieldset
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
      } else if (field === "Categories") {
        const row = document.createElement("div");
        row.className = "form-field";
        const label = document.createElement("label");
        label.textContent = "Categories";
        label.setAttribute("for", "field-Categories");
        const input = document.createElement("input");
        input.type = "text";
        input.id = "field-Categories";
        input.name = "Categories";
        const cats = item.Categories;
        input.value = Array.isArray(cats) ? cats.join(", ") : (cats || "");
        row.appendChild(label);
        row.appendChild(input);
        editFormFields.appendChild(row);
      } else if (field === "description") {
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
      } else {
        const row = document.createElement("div");
        row.className = "form-field";
        const label = document.createElement("label");
        label.textContent = field;
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
    });

    editFormContainer.style.display = "";
    editFormContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function hideEditForm() {
    editFormContainer.style.display = "none";
    currentIndex = null;
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
        const input = document.getElementById("field-Categories");
        const val = input ? input.value.trim() : "";
        item.Categories = val ? val.split(",").map((s) => s.trim()).filter(Boolean) : [];
      } else {
        const el = document.getElementById("field-" + field);
        item[field] = el ? el.value : "";
      }
    });

    return item;
  }

  function buildPropagation(item) {
    // Only for blog posts with an author and a stored original
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
    if (currentIndex === null) return;
    const item = collectFormValues();

    // Check for author-level propagation
    const propagate = buildPropagation(item);
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
      index: currentIndex,
      item: item,
      backup_created: backupCreated
    };
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
          hideEditForm();
          initFuse();
          const propCount = data.propagated || 0;
          let msg = "Saved successfully.";
          if (propCount > 0) msg += " Updated " + propCount + " other post" + (propCount === 1 ? "" : "s") + ".";
          showStatus(msg, false);
          // Restore search/recent view
          if (searchInput.value.trim()) {
            runSearch(searchInput.value.trim());
          } else {
            showRecentItems();
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
