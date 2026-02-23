(function () {
  "use strict";

  let allData = [];
  let showcaseData = [];
  let fuse = null;
  let currentType = null;
  let currentIndex = null; // index into allData (null = create mode)
  let currentMode = "create"; // "edit" or "create"
  let backupCreated = false;
  let originalItem = null; // snapshot before editing
  let uniqueAuthors = []; // for autocomplete
  let uniqueCategories = []; // for checkbox list

  // Fields eligible for author-level propagation (empty→non-empty triggers prompt)
  const PROPAGATABLE_FIELDS = ["AuthorSiteDescription", "rssLink", "favicon"];
  const PROPAGATABLE_SOCIAL = ["mastodon", "bluesky", "youtube", "github", "linkedin"];

  // Slugify — mirrors @sindresorhus/slugify with default options
  // Replacements applied before NFD diacritic stripping (mirrors @sindresorhus/transliterate)
  const SLUGIFY_REPLACEMENTS = new Map([
    ["&", " and "], ["\u{1F984}", " unicorn "], ["\u2665", " love "],
    // German umlauts (must come before NFD which would strip to base letter)
    ["\u00E4", "ae"], ["\u00C4", "Ae"],
    ["\u00F6", "oe"], ["\u00D6", "Oe"],
    ["\u00FC", "ue"], ["\u00DC", "Ue"],
    ["\u00DF", "ss"], ["\u1E9E", "Ss"],
    // Ligatures and special Latin
    ["\u00E6", "ae"], ["\u00C6", "AE"],
    ["\u0153", "oe"], ["\u0152", "OE"],
    ["\u00F8", "o"], ["\u00D8", "O"],
    ["\u0142", "l"], ["\u0141", "L"],
    ["\u00F0", "d"], ["\u00D0", "D"],
    ["\u00FE", "th"], ["\u00DE", "TH"],
    ["\u0111", "d"], ["\u0110", "D"],
  ]);
  function slugify(text) {
    // Custom replacements (& → and, etc.)
    for (const [key, value] of SLUGIFY_REPLACEMENTS) {
      text = text.replaceAll(key, value);
    }
    // Transliterate: NFD decompose, strip diacritics, normalize dashes
    text = text.normalize("NFD").replace(/\p{Diacritic}/gu, "").normalize();
    text = text.replace(/\p{Dash_Punctuation}/gu, "-");
    // Decamelize: split camelCase into separate words
    text = text
      .replaceAll(/([A-Z]{2,})(\d+)/g, "$1 $2")
      .replaceAll(/([a-z\d]+)([A-Z]{2,})/g, "$1 $2")
      .replaceAll(/([a-z\d])([A-Z])/g, "$1 $2")
      .replaceAll(/([A-Z]+)([A-Z][a-rt-z\d]+)/g, "$1 $2");
    // Lowercase
    text = text.toLowerCase();
    // Handle contractions: 's → s, 't → t (straight and curly apostrophes)
    text = text.replaceAll(/([a-z\d]+)['\u2019]([ts])(\s|$)/g, "$1$2$3");
    // Replace non-alphanumeric runs with separator
    text = text.replace(/[^a-z\d]+/g, "-");
    // Remove leading/trailing separators and collapse duplicates
    text = text.replace(/^-|-$/g, "");
    return text;
  }

  // Field order per type
  const FIELD_ORDER = {
    "blog post": [
      "Issue", "Type", "Title", "Link", "Date", "Author", "Categories",
      "formattedDate", "slugifiedAuthor", "slugifiedTitle",
      "description", "AuthorSite", "AuthorSiteDescription", "socialLinks",
      "favicon", "rssLink"
    ],
    site: [
      "Issue", "Type", "Title", "Link", "Date",
      "formattedDate", "description", "favicon", "screenshotpath", "leaderboardLink"
    ],
    release: [
      "Issue", "Type", "Title", "Link", "Date",
      "formattedDate", "description"
    ],
    starter: [
      "Issue", "Type", "Title", "Link", "Demo",
      "description", "screenshotpath"
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
  const btnSaveEnd = document.getElementById("btn-save-end");
  const btnSaveDeploy = document.getElementById("btn-save-deploy");
  const btnCancel = document.getElementById("btn-cancel");
  const btnViewJson = document.getElementById("btn-view-json");
  const jsonPreviewPanel = document.getElementById("json-preview-panel");
  const deleteConfirmModal = document.getElementById("delete-confirm-modal");
  const deleteConfirmMessage = document.getElementById("delete-confirm-message");
  const deleteConfirmOk = document.getElementById("delete-confirm-ok");
  const deleteConfirmCancel = document.getElementById("delete-confirm-cancel");
  const dupLinkModal = document.getElementById("duplicate-link-modal");
  const dupLinkMessage = document.getElementById("duplicate-link-message");
  const dupLinkOk = document.getElementById("duplicate-link-ok");
  const statusMessage = document.getElementById("status-message");
  const deployModal = document.getElementById("deploy-modal");
  const deployModalTitle = document.getElementById("deploy-modal-title");
  const deployModalOutput = document.getElementById("deploy-modal-output");
  const deployModalOk = document.getElementById("deploy-modal-ok");
  const btnRunLatest = document.getElementById("btn-run-latest");
  const btnDeploy = document.getElementById("btn-deploy");
  const btnCheckUrlOpen = document.getElementById("btn-check-url-open");
  const checkUrlInput = document.getElementById("check-url-input");
  const btnCheckUrl = document.getElementById("btn-check-url");
  const checkUrlModal = document.getElementById("check-url-modal");
  const checkUrlResult = document.getElementById("check-url-result");
  const checkUrlModalClose = document.getElementById("check-url-modal-close");
  const testDataBanner = document.getElementById("test-data-banner");
  const testWarnModal = document.getElementById("test-warn-modal");
  const testWarnProceed = document.getElementById("test-warn-proceed");
  const testWarnCancel = document.getElementById("test-warn-cancel");
  const testDeployModal = document.getElementById("test-deploy-modal");
  const testDeployDelete = document.getElementById("test-deploy-delete");
  const testDeployClose = document.getElementById("test-deploy-close");

  // Load data on page load
  fetch("/editor/data")
    .then((r) => r.json())
    .then((data) => {
      allData = data.bundledb;
      showcaseData = data.showcase || [];
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

  // --- Test data helpers ---

  function hasTestData() {
    return allData.some((e) => (e.Title || "").toLowerCase().includes("bobdemo99"));
  }

  function getTestDataCount() {
    return allData.filter((e) => (e.Title || "").toLowerCase().includes("bobdemo99")).length;
  }

  function updateTestDataBanner() {
    if (!currentType || !hasTestData()) {
      testDataBanner.style.display = "none";
      return;
    }
    const count = getTestDataCount();
    testDataBanner.innerHTML = "";
    testDataBanner.style.display = "";

    const msg = document.createElement("span");
    msg.className = "test-data-message";
    msg.textContent = count + " test " + (count === 1 ? "entry" : "entries") + " (bobDemo99) present in database";
    testDataBanner.appendChild(msg);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-action btn-delete-entry";
    btn.textContent = "DELETE ALL TEST ITEMS";
    btn.addEventListener("click", () => {
      deleteConfirmMessage.textContent =
        "ARE YOU SURE YOU WANT TO DELETE ALL " + count + " TEST ENTRIES?";
      deleteConfirmOk.onclick = () => {
        deleteConfirmModal.style.display = "none";
        deleteAllTestEntries();
      };
      deleteConfirmModal.style.display = "";
      deleteConfirmCancel.focus();
    });
    testDataBanner.appendChild(btn);
  }

  // Modal event listeners for test data modals
  testWarnCancel.addEventListener("click", () => {
    testWarnModal.style.display = "none";
  });
  testDeployClose.addEventListener("click", () => {
    testDeployModal.style.display = "none";
  });

  function guardRunLatest(callback) {
    if (!hasTestData()) { callback(); return; }
    testWarnModal.style.display = "";
    testWarnProceed.onclick = () => {
      testWarnModal.style.display = "none";
      callback();
    };
    testWarnProceed.focus();
  }

  function guardDeploy(callback) {
    if (!hasTestData()) { callback(); return; }
    testDeployModal.style.display = "";
    testDeployDelete.onclick = () => {
      testDeployModal.style.display = "none";
      deleteAllTestEntries();
    };
    testDeployDelete.focus();
  }

  // Mode change handler
  modeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      currentMode = radio.value;
      currentType = null;
      typeRadios.forEach((r) => { r.checked = false; });
      hideEditForm();
      searchInput.value = "";
      searchResults.style.display = "none";
      recentItems.style.display = "none";
      searchSection.style.display = "none";
      testDataBanner.style.display = "none";
    });
  });

  // Type change handler
  typeRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
      currentType = radio.value;
      searchInput.value = "";
      hideEditForm();
      updateTestDataBanner();

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
  btnSave.addEventListener("click", () => saveItem());

  // --- Run Latest / Deploy shared flows ---

  function runLatestFlow() {
    deployModalTitle.textContent = "Running end-session scripts...";
    deployModalOutput.textContent = "";
    deployModalOk.style.display = "none";
    deployModal.style.display = "";

    return fetch("/editor/end-session", { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) {
          deployModalTitle.textContent = "End-session scripts failed";
          deployModalOk.textContent = "Ok";
          deployModalOk.onclick = () => { deployModal.style.display = "none"; };
          deployModalOk.style.display = "";
          return;
        }
        const scripts = [
          ["genissuerecords", "Issue Records"],
          ["generate_insights", "Insights"],
          ["generate_latest_data", "Latest Data"]
        ];
        const lines = scripts.map(([key, label]) => {
          const r = data[key];
          return label + ": " + (r && r.success ? "OK" : "FAILED");
        });
        deployModalOutput.textContent = lines.join("\n");

        deployModalTitle.textContent = "Starting local server...";
        return fetch("/editor/run-latest", { method: "POST" })
          .then((r) => r.json())
          .then((result) => {
            if (!result.success) {
              deployModalTitle.textContent = "Server failed to start";
              deployModalOutput.textContent += "\n\n" + (result.error || "Unknown error");
              deployModalOk.textContent = "Ok";
              deployModalOk.onclick = () => { deployModal.style.display = "none"; };
              deployModalOk.style.display = "";
              return;
            }
            deployModalTitle.textContent = "Verifying site build...";
            deployModalOutput.textContent += "\n\nServer running at localhost:8080";
            return fetch("/editor/verify-site", { method: "POST" })
              .then((r) => r.json())
              .then((verify) => {
                if (verify.success) {
                  deployModalOutput.textContent += "\n\nSITE VERIFICATION SUCCESSFUL!";
                } else {
                  deployModalOutput.textContent += "\n\n" + verify.report;
                }
                if (verify.git_result) {
                  deployModalOutput.textContent += "\n" + verify.git_result.message;
                }
                deployModalTitle.textContent = verify.success ? "Local server ready" : "Verification issues found";
                deployModalOk.textContent = "View Local Site";
                deployModalOk.onclick = () => {
                  deployModal.style.display = "none";
                  window.open("http://localhost:8080", "_blank");
                };
                deployModalOk.style.display = "";
              });
          });
      })
      .catch((err) => {
        deployModalTitle.textContent = "Failed";
        deployModalOutput.textContent = "Error: " + err.message;
        deployModalOk.textContent = "Ok";
        deployModalOk.onclick = () => { deployModal.style.display = "none"; };
        deployModalOk.style.display = "";
      });
  }

  function runDeployFlow() {
    deployModalTitle.textContent = "Deploying...";
    deployModalOutput.textContent = "Running npm run deploy...\n";
    deployModalOk.style.display = "none";
    deployModal.style.display = "";

    return fetch("/editor/deploy", { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        deployModalTitle.textContent = data.success ? "Deploy Complete" : "Deploy Failed";
        let output = data.output || "(no output)";
        if (data.git_result) {
          output += data.git_result.success
            ? "\n\n" + data.git_result.message
            : "\n\nNote: DB commit/push failed: " + data.git_result.message;
        }
        deployModalOutput.textContent = output;
        deployModalOutput.scrollTop = deployModalOutput.scrollHeight;
        deployModalOk.textContent = "View 11tybundle.dev";
        deployModalOk.onclick = () => {
          deployModal.style.display = "none";
          if (data.success) window.open("https://11tybundle.dev", "_blank");
        };
        deployModalOk.style.display = "";
      })
      .catch((err) => {
        deployModalTitle.textContent = "Deploy Failed";
        deployModalOutput.textContent = "Error: " + err.message;
        deployModalOk.textContent = "Ok";
        deployModalOk.onclick = () => { deployModal.style.display = "none"; };
        deployModalOk.style.display = "";
      });
  }

  // Save & Run Latest handler
  btnSaveEnd.addEventListener("click", () => {
    saveItem(() => {
      guardRunLatest(() => {
        btnSaveEnd.disabled = true;
        btnSaveEnd.textContent = "Running scripts...";
        runLatestFlow().finally(() => {
          btnSaveEnd.disabled = false;
          btnSaveEnd.textContent = "Save & Run Latest";
        });
      });
    });
  });

  // Save & Deploy handler
  btnSaveDeploy.addEventListener("click", () => {
    saveItem(() => {
      guardDeploy(() => {
        btnSaveDeploy.disabled = true;
        btnSaveDeploy.textContent = "Deploying...";
        runDeployFlow().finally(() => {
          btnSaveDeploy.disabled = false;
          btnSaveDeploy.textContent = "Save & Deploy";
        });
      });
    });
  });

  // Standalone Run Latest handler (header button, no save)
  btnRunLatest.addEventListener("click", () => {
    guardRunLatest(() => {
      btnRunLatest.disabled = true;
      btnRunLatest.textContent = "Running...";
      runLatestFlow().finally(() => {
        btnRunLatest.disabled = false;
        btnRunLatest.textContent = "Run Latest";
      });
    });
  });

  // Standalone Deploy handler (header button, no save)
  btnDeploy.addEventListener("click", () => {
    guardDeploy(() => {
      btnDeploy.disabled = true;
      btnDeploy.textContent = "Deploying...";
      runDeployFlow().finally(() => {
        btnDeploy.disabled = false;
        btnDeploy.textContent = "Deploy";
      });
    });
  });

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

  // View JSON handler
  btnViewJson.addEventListener("click", () => {
    const item = collectFormValues();
    let html = "<h4>bundledb.json entry</h4>";

    // For sites, strip screenshotpath and leaderboardLink from bundledb preview (they go to showcase-data)
    const bundleItem = Object.assign({}, item);
    let screenshotpath = "";
    let leaderboardLink = "";
    if (currentType === "site") {
      screenshotpath = bundleItem.screenshotpath || "";
      leaderboardLink = bundleItem.leaderboardLink || "";
      delete bundleItem.screenshotpath;
      delete bundleItem.leaderboardLink;
    }
    html += "<pre>" + escapeHtml(JSON.stringify(bundleItem, null, 2)) + "</pre>";

    if (currentType === "site") {
      html += "<h4>showcase-data.json entry</h4>";
      const showcaseEntry = {
        title: item.Title || "",
        description: item.description || "",
        link: item.Link || "",
        date: item.Date || "",
        formattedDate: item.formattedDate || "",
        favicon: item.favicon || "",
        screenshotpath: screenshotpath,
        leaderboardLink: leaderboardLink,
      };
      html += "<pre>" + escapeHtml(JSON.stringify(showcaseEntry, null, 2)) + "</pre>";
    }

    jsonPreviewPanel.innerHTML = html;
    jsonPreviewPanel.style.display = "";
    jsonPreviewPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Duplicate link detection
  // Delete confirmation modal
  deleteConfirmCancel.addEventListener("click", () => {
    deleteConfirmModal.style.display = "none";
  });

  dupLinkOk.addEventListener("click", () => {
    dupLinkModal.style.display = "none";
  });

  // Check URL
  btnCheckUrlOpen.addEventListener("click", () => {
    checkUrlInput.value = "";
    checkUrlResult.style.display = "none";
    checkUrlResult.innerHTML = "";
    checkUrlModal.style.display = "flex";
    setTimeout(() => checkUrlInput.focus(), 50);
  });

  function doCheckUrl() {
    const url = checkUrlInput.value.trim();
    if (!url) return;
    btnCheckUrl.textContent = "Checking...";
    btnCheckUrl.disabled = true;
    fetch("/editor/check-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.found && data.found.length > 0) {
          let html = "<p><strong>URL found in:</strong></p><ul>";
          for (const match of data.found) {
            html += `<li><strong>${match.source}</strong>`;
            if (match.type) html += ` &mdash; ${match.type}`;
            if (match.title) html += `: ${match.title}`;
            html += "</li>";
          }
          html += "</ul>";
          checkUrlResult.innerHTML = html;
        } else {
          checkUrlResult.innerHTML =
            "<p>URL not found in bundledb.json or showcase-data.json.</p>";
        }
        checkUrlResult.style.display = "block";
      })
      .catch((err) => {
        checkUrlResult.innerHTML = `<p class="status-error">Error: ${err.message}</p>`;
        checkUrlResult.style.display = "block";
      })
      .finally(() => {
        btnCheckUrl.textContent = "Check";
        btnCheckUrl.disabled = false;
      });
  }

  btnCheckUrl.addEventListener("click", doCheckUrl);
  checkUrlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      doCheckUrl();
    }
  });
  checkUrlModalClose.addEventListener("click", () => {
    checkUrlModal.style.display = "none";
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && checkUrlModal.style.display !== "none") {
      checkUrlModal.style.display = "none";
    }
  });

  function normalizeLink(url) {
    let s = url.trim().toLowerCase().replace(/\/+$/, "");
    // Ensure protocol so www. stripping works consistently
    if (!/^https?:\/\//.test(s)) s = "https://" + s;
    return s.replace(/^(https?:\/\/)www\./, "$1");
  }

  function findDuplicateLink(link) {
    if (!link) return null;
    const normalized = normalizeLink(link);
    const sources = [];
    let matchEntry = null;

    for (const entry of allData) {
      const existing = normalizeLink(entry.Link || "");
      if (existing && existing === normalized) {
        matchEntry = { Type: entry.Type, Title: entry.Title };
        sources.push("bundledb.json");
        break;
      }
    }

    for (const entry of showcaseData) {
      const existing = normalizeLink(entry.link || "");
      if (existing && existing === normalized) {
        if (!matchEntry) matchEntry = { Type: "site", Title: entry.title };
        if (!sources.includes("showcase-data.json")) sources.push("showcase-data.json");
        break;
      }
    }

    if (!matchEntry) return null;
    matchEntry.sources = sources;
    return matchEntry;
  }

  function showDuplicateLinkWarning(link, existing) {
    const type = existing.Type || "entry";
    const title = existing.Title || "(untitled)";
    const files = existing.sources ? existing.sources.join(" and ") : "bundledb.json";
    dupLinkMessage.textContent =
      "This link already exists as a " + type + ' in ' + files + ': "' + title + '".';
    dupLinkModal.style.display = "";
  }

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
      item.leaderboardLink = "";
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
    lastFetchedUrl = "";

    // Hide search/recent
    recentItems.style.display = "none";
    searchResults.style.display = "none";

    // Skip checkbox + Delete button (edit mode only)
    if (!isCreate) {
      const skipRow = document.createElement("div");
      skipRow.className = "form-field-skip";

      const skipLeft = document.createElement("div");
      skipLeft.className = "skip-left";
      const skipCb = document.createElement("input");
      skipCb.type = "checkbox";
      skipCb.id = "field-Skip";
      skipCb.checked = item.Skip === true;
      const skipLabel = document.createElement("label");
      skipLabel.textContent = "Skip (exclude from site generation)";
      skipLabel.setAttribute("for", "field-Skip");
      skipLeft.appendChild(skipCb);
      skipLeft.appendChild(skipLabel);

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn-action btn-delete-entry";
      deleteBtn.textContent = "DELETE ENTRY";
      deleteBtn.addEventListener("click", () => {
        const entryType = (currentType || "entry").toUpperCase();
        const entryTitle = item.Title || "(untitled)";
        deleteConfirmMessage.textContent =
          'ARE YOU SURE YOU WANT TO DELETE THE ' + entryType + ' NAMED "' + entryTitle + '"?';
        deleteConfirmOk.onclick = () => {
          deleteConfirmModal.style.display = "none";
          deleteEntry(currentIndex);
        };
        deleteConfirmModal.style.display = "";
        deleteConfirmCancel.focus();
      });

      const btnGroup = document.createElement("div");
      btnGroup.className = "skip-right";
      btnGroup.appendChild(deleteBtn);

      const testCount = allData.filter((e) =>
        (e.Title || "").toLowerCase().includes("bobdemo99")
      ).length;
      if (testCount > 0) {
        const deleteTestBtn = document.createElement("button");
        deleteTestBtn.type = "button";
        deleteTestBtn.className = "btn-action btn-delete-entry";
        deleteTestBtn.textContent = "DELETE ALL TEST ENTRIES";
        deleteTestBtn.addEventListener("click", () => {
          deleteConfirmMessage.textContent =
            "ARE YOU SURE YOU WANT TO DELETE ALL " + testCount + " TEST ENTRIES?";
          deleteConfirmOk.onclick = () => {
            deleteConfirmModal.style.display = "none";
            deleteAllTestEntries();
          };
          deleteConfirmModal.style.display = "";
          deleteConfirmCancel.focus();
        });
        btnGroup.appendChild(deleteTestBtn);
      }

      skipRow.appendChild(skipLeft);
      skipRow.appendChild(btnGroup);
      editFormFields.appendChild(skipRow);
    }

    fields.forEach((field) => {
      // Type is already selected via radio button in create mode
      if (field === "Type" && isCreate) return;
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

      // Insert fetch buttons after Date field
      if (field === "Date" && currentType === "site") {
        const allPopulated = item.description && item.favicon && item.screenshotpath && item.leaderboardLink;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-action btn-fetch-data";
        btn.textContent = allPopulated
          ? "Refresh Description, Favicon, Screenshot & Leaderboard"
          : "Fetch Description, Favicon, Screenshot & Leaderboard";
        btn.addEventListener("click", () => { lastFetchedUrl = ""; fetchSiteData(); });
        editFormFields.appendChild(btn);
      }
      if (field === "Date" && currentType === "release") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-action btn-fetch-data";
        btn.textContent = item.description ? "Refresh Description" : "Fetch Description";
        btn.addEventListener("click", () => { lastFetchedUrl = ""; fetchDescriptionOnly(); });
        editFormFields.appendChild(btn);
      }
      if (field === "Demo" && currentType === "starter") {
        const allPopulated = item.description && item.screenshotpath;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-action btn-fetch-data";
        btn.textContent = allPopulated
          ? "Refresh Description & Screenshot"
          : "Fetch Description & Screenshot";
        btn.addEventListener("click", () => { lastFetchedUrl = ""; fetchStarterData(); });
        editFormFields.appendChild(btn);
      }
      if (field === "Categories" && currentType === "blog post" && !item.description) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-action btn-fetch-data";
        btn.textContent = "Fetch Description";
        btn.addEventListener("click", () => { lastFetchedUrl = ""; fetchDescriptionOnly(); });
        editFormFields.appendChild(btn);
      }
      // Auto-populate AuthorSite with origin of Link for blog post creates
      if (field === "AuthorSite" && currentType === "blog post") {
        const asEl = document.getElementById("field-AuthorSite");
        if (asEl && !asEl.value.trim()) {
          const linkEl = document.getElementById("field-Link");
          if (linkEl && linkEl.value.trim()) {
            try {
              const origin = new URL(linkEl.value.trim()).origin;
              asEl.value = origin;
            } catch { /* invalid URL, leave empty */ }
          }
        }
        // Insert Fetch/Refresh Author Info button
        const authorBtn = document.createElement("button");
        authorBtn.type = "button";
        authorBtn.id = "btn-fetch-author-info";
        authorBtn.className = "btn-action btn-fetch-data";
        const authorEl = document.getElementById("field-Author");
        const authorName = authorEl ? authorEl.value.trim() : (item.Author || "");
        authorBtn.textContent = uniqueAuthors.includes(authorName)
          ? "Refresh Author Info" : "Fetch Author Info";
        authorBtn.addEventListener("click", fetchAuthorInfo);
        editFormFields.appendChild(authorBtn);
      }
    });

    // Auto-slugify Title → slugifiedTitle, Author → slugifiedAuthor
    if (currentType === "blog post") {
      const titleField = document.getElementById("field-Title");
      const slugTitleField = document.getElementById("field-slugifiedTitle");
      if (titleField && slugTitleField) {
        titleField.addEventListener("blur", () => {
          if (titleField.value.trim() && !slugTitleField.value.trim()) {
            slugTitleField.value = slugify(titleField.value);
          }
        });
      }
      const authorField = document.getElementById("field-Author");
      const slugAuthorField = document.getElementById("field-slugifiedAuthor");
      if (authorField && slugAuthorField) {
        authorField.addEventListener("blur", () => {
          if (authorField.value.trim() && !slugAuthorField.value.trim()) {
            slugAuthorField.value = slugify(authorField.value);
          }
        });
      }
    }

    // Auto-update formattedDate when Date changes
    const dateField = document.getElementById("field-Date");
    const fmtDateField = document.getElementById("field-formattedDate");
    if (dateField && fmtDateField) {
      dateField.addEventListener("blur", () => {
        const val = dateField.value.trim();
        if (val) {
          // Parse YYYY-MM-DD as local time (not UTC) to avoid off-by-one
          const parts = val.match(/^(\d{4})-(\d{2})-(\d{2})/);
          if (parts) {
            const parsed = new Date(+parts[1], +parts[2] - 1, +parts[3]);
            fmtDateField.value = formatDate(parsed);
          }
        }
      });
    }

    // Check for duplicate Link on blur (create mode only)
    if (isCreate) {
      const linkField = document.getElementById("field-Link");
      if (linkField) {
        linkField.addEventListener("blur", () => {
          const dup = findDuplicateLink(linkField.value);
          if (dup) showDuplicateLinkWarning(linkField.value, dup);
        });
      }
    }

    // Show View JSON button; reset panel
    btnViewJson.style.display = "";
    jsonPreviewPanel.style.display = "none";
    jsonPreviewPanel.innerHTML = "";

    editFormContainer.style.display = "";
    editFormContainer.scrollIntoView({ behavior: "smooth", block: "start" });

    if (isCreate) {
      const titleField = document.getElementById("field-Title");
      if (titleField) titleField.focus();
    }
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

    // Set row count so CSS grid-auto-flow: column fills alphabetically down columns
    const cols = 5;
    const rows = Math.ceil(uniqueCategories.length / cols);
    grid.style.gridTemplateRows = "repeat(" + rows + ", auto)";

    // Display aliases for long category names (value stored is unchanged)
    const categoryDisplayNames = {
      "Internationalization": "i18n",
      "Migrating to Eleventy": "Migrating to 11ty",
      "The 11ty Conference 2024": "11ty Conf 2024",
    };

    uniqueCategories.forEach((cat) => {
      const lbl = document.createElement("label");
      lbl.className = "category-checkbox";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.name = "cat-checkbox";
      cb.value = cat;
      cb.checked = selected.has(cat);
      lbl.appendChild(cb);
      lbl.appendChild(document.createTextNode(" " + (categoryDisplayNames[cat] || cat)));
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
    const isExisting = name && uniqueAuthors.includes(name);

    // Rename the author info button based on whether author is known
    const authorBtn = document.getElementById("btn-fetch-author-info");
    if (authorBtn) {
      authorBtn.textContent = isExisting ? "Refresh Author Info" : "Fetch Author Info";
    }

    if (!isExisting) {
      // New author: auto-populate AuthorSite with origin of Link URL if empty
      const asEl = document.getElementById("field-AuthorSite");
      if (asEl && !asEl.value.trim()) {
        const linkEl = document.getElementById("field-Link");
        if (linkEl && linkEl.value.trim()) {
          try {
            asEl.value = new URL(linkEl.value.trim()).origin;
          } catch { /* invalid URL, leave empty */ }
        }
      }
      return;
    }

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

  const fieldDisplayNames = {
    "formattedDate": "Formatted Date",
    "slugifiedAuthor": "Slugified Author",
    "slugifiedTitle": "Slugified Title",
    "AuthorSite": "Author Site",
    "AuthorSiteDescription": "Author Site Description",
  };

  function fieldLabel(field) {
    if (field === "Link" && (currentType === "release" || currentType === "starter")) {
      return "GitHub repo link";
    }
    if (field === "Demo" && currentType === "starter") {
      return "Link to demo site";
    }
    return fieldDisplayNames[field] || field;
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
    const raw = item[field] != null ? String(item[field]) : "";
    if (field === "Date" && raw.includes("T")) {
      input.value = raw.slice(0, 10);
      input.dataset.fullDate = raw;
    } else {
      input.value = raw;
    }
    row.appendChild(label);
    row.appendChild(input);
    editFormFields.appendChild(row);
  }

  function hideEditForm() {
    editFormContainer.style.display = "none";
    currentIndex = null;
    jsonPreviewPanel.style.display = "none";
    jsonPreviewPanel.innerHTML = "";
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
        if (field === "Type" && !el) {
          item[field] = currentType;
        } else if (field === "Date" && el && el.dataset.fullDate) {
          item[field] = el.dataset.fullDate;
        } else {
          item[field] = el ? el.value : "";
        }
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

  function deleteEntry(index) {
    fetch("/editor/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: index, backup_created: backupCreated })
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          backupCreated = data.backup_created;
          allData.splice(index, 1);
          hideEditForm();
          initFuse();
          showStatus("Entry deleted.", false);
          if (currentMode === "edit") {
            if (searchInput.value.trim()) {
              runSearch(searchInput.value.trim());
            } else {
              showRecentItems();
            }
          }
        } else {
          showStatus("Delete failed: " + (data.error || "Unknown error"), true);
        }
      })
      .catch((err) => {
        showStatus("Delete failed: " + err.message, true);
      });
  }

  function deleteAllTestEntries() {
    fetch("/editor/delete-test-entries", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backup_created: backupCreated })
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          backupCreated = data.backup_created;
          allData = allData.filter((e) =>
            !(e.Title || "").toLowerCase().includes("bobdemo99")
          );
          hideEditForm();
          initFuse();
          updateTestDataBanner();
          showStatus("Deleted " + data.deleted + " test entries.", false);
          if (currentMode === "edit") {
            if (searchInput.value.trim()) {
              runSearch(searchInput.value.trim());
            } else {
              showRecentItems();
            }
          }
        } else {
          showStatus("Delete failed: " + (data.error || "Unknown error"), true);
        }
      })
      .catch((err) => {
        showStatus("Delete failed: " + err.message, true);
      });
  }

  function saveItem(onSuccess) {
    const isCreate = currentIndex === null;

    if (!isCreate && currentIndex === null) return;

    const item = collectFormValues();

    // Block save if link is a duplicate (create mode)
    if (isCreate && item.Link) {
      const dup = findDuplicateLink(item.Link);
      if (dup) {
        showDuplicateLinkWarning(item.Link, dup);
        return;
      }
    }

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
    btnSaveEnd.disabled = true;
    btnSaveDeploy.disabled = true;
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
          if (!onSuccess) showStatus(msg, false);
          if (onSuccess) onSuccess();

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
        btnSaveEnd.disabled = false;
        btnSaveDeploy.disabled = false;
        btnSave.textContent = "Save";
      });
  }

  // --- Site create: fetch favicon, screenshot & description ---

  let lastFetchedUrl = "";

  function fetchSiteData() {
    const linkEl = document.getElementById("field-Link");
    const url = linkEl ? linkEl.value.trim() : "";
    if (!url) {
      showStatus("Enter a Link first.", true);
      return;
    }

    // Avoid re-fetching for the same URL
    if (url === lastFetchedUrl) return;
    lastFetchedUrl = url;

    const btn = editFormFields.querySelector(".btn-fetch-data");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Fetching...";
    }

    showStatus("Fetching site data...", false);

    // Fetch favicon, screenshot, and description in parallel
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

    const descriptionPromise = fetch("/editor/description", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    const leaderboardPromise = fetch("/editor/leaderboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    Promise.all([faviconPromise, screenshotPromise, descriptionPromise, leaderboardPromise]).then(([favResult, ssResult, descResult, lbResult]) => {
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

      if (descResult.success && descResult.description) {
        const descEl = document.getElementById("field-description");
        if (descEl) descEl.value = descResult.description;
      }

      if (lbResult.success && lbResult.leaderboard_link) {
        const lbEl = document.getElementById("field-leaderboardLink");
        if (lbEl) lbEl.value = lbResult.leaderboard_link;
      }

      let msgs = [];
      if (favResult.success) msgs.push("Favicon fetched");
      else msgs.push("Favicon failed");
      if (ssResult.success) msgs.push("Screenshot captured");
      else msgs.push("Screenshot failed");
      if (descResult.success) msgs.push("Description extracted");
      else msgs.push("Description failed");
      if (lbResult.success && lbResult.leaderboard_link) msgs.push("Leaderboard found");
      else if (lbResult.success) msgs.push("No leaderboard entry");
      else msgs.push("Leaderboard check failed");
      showStatus(msgs.join(". ") + ".", !favResult.success && !ssResult.success && !descResult.success);
    }).finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Fetch Description, Favicon, Screenshot & Leaderboard";
      }
    });
  }

  function fetchStarterData() {
    const demoEl = document.getElementById("field-Demo");
    const url = demoEl ? demoEl.value.trim() : "";
    if (!url) {
      showStatus("Enter a Demo link first.", true);
      return;
    }

    if (url === lastFetchedUrl) return;
    lastFetchedUrl = url;

    const btn = editFormFields.querySelector(".btn-fetch-data");
    const origLabel = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Fetching...";
    }

    showStatus("Fetching starter data...", false);

    const descriptionPromise = fetch("/editor/description", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    const screenshotPromise = fetch("/editor/screenshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).catch(() => ({ success: false }));

    Promise.all([descriptionPromise, screenshotPromise]).then(([descResult, ssResult]) => {
      if (descResult.success && descResult.description) {
        const descEl = document.getElementById("field-description");
        if (descEl) descEl.value = descResult.description;
      }

      if (ssResult.success && ssResult.screenshotpath) {
        const ssEl = document.getElementById("field-screenshotpath");
        if (ssEl) ssEl.value = ssResult.screenshotpath;

        if (ssResult.filename) {
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
      if (descResult.success) msgs.push("Description extracted");
      else msgs.push("Description failed");
      if (ssResult.success) msgs.push("Screenshot captured");
      else msgs.push("Screenshot failed");
      showStatus(msgs.join(". ") + ".", !descResult.success && !ssResult.success);
    }).finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = origLabel;
      }
    });
  }

  function fetchDescriptionOnly() {
    const linkEl = document.getElementById("field-Link");
    const url = linkEl ? linkEl.value.trim() : "";
    if (!url) {
      showStatus("Enter a Link first.", true);
      return;
    }

    if (url === lastFetchedUrl) return;
    lastFetchedUrl = url;

    const btn = editFormFields.querySelector(".btn-fetch-data");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Fetching...";
    }

    showStatus("Fetching description...", false);

    fetch("/editor/description", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).then((result) => {
      if (result.success && result.description) {
        const descEl = document.getElementById("field-description");
        if (descEl && !descEl.value.trim()) {
          descEl.value = result.description;
        }
        showStatus("Description extracted.", false);
      } else {
        showStatus("Description failed.", true);
      }
    }).catch(() => {
      showStatus("Description failed.", true);
    }).finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Fetch Description";
      }
    });
  }

  function fetchAuthorInfo() {
    const asEl = document.getElementById("field-AuthorSite");
    const url = asEl ? asEl.value.trim() : "";
    if (!url) {
      showStatus("Enter an AuthorSite first.", true);
      return;
    }

    const btn = document.getElementById("btn-fetch-author-info");
    const origLabel = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Fetching...";
    }

    showStatus("Fetching author info...", false);

    fetch("/editor/author-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    }).then((r) => r.json()).then((result) => {
      if (!result.success) {
        showStatus("Author info fetch failed.", true);
        return;
      }

      let msgs = [];

      if (result.description) {
        const el = document.getElementById("field-AuthorSiteDescription");
        if (el && !el.value.trim()) el.value = result.description;
        msgs.push("Description");
      }

      if (result.favicon) {
        const el = document.getElementById("field-favicon");
        if (el && !el.value.trim()) el.value = result.favicon;
        msgs.push("Favicon");
      }

      if (result.rssLink) {
        const el = document.getElementById("field-rssLink");
        if (el && !el.value.trim()) el.value = result.rssLink;
        msgs.push("RSS link");
      }

      if (result.socialLinks) {
        const sl = result.socialLinks;
        if (sl.mastodon) {
          const el = document.getElementById("field-sl-mastodon");
          if (el && !el.value.trim()) el.value = sl.mastodon;
          msgs.push("Mastodon");
        }
        if (sl.bluesky) {
          const el = document.getElementById("field-sl-bluesky");
          if (el && !el.value.trim()) el.value = sl.bluesky;
          msgs.push("Bluesky");
        }
      }

      if (msgs.length) {
        showStatus("Fetched: " + msgs.join(", ") + ".", false);
      } else {
        showStatus("No author info found.", true);
      }
    }).catch(() => {
      showStatus("Author info fetch failed.", true);
    }).finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = origLabel;
      }
    });
  }

  function showStatus(msg, isError, timeout) {
    statusMessage.style.whiteSpace = msg.includes("\n") ? "pre-wrap" : "";
    statusMessage.textContent = msg;
    statusMessage.className = isError ? "status-error" : "status-success";
    statusMessage.style.display = "";
    setTimeout(() => {
      statusMessage.style.display = "none";
    }, timeout || 4000);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
