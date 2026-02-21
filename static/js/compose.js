document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("compose-form");
    const textarea = document.getElementById("post-text");
    const cbMastodon = document.getElementById("cb-mastodon");
    const cbBluesky = document.getElementById("cb-bluesky");
    const cbDiscord = document.getElementById("cb-discord");
    const cwMastodonSection = document.getElementById("cw-mastodon-section");
    const cwBlueskySection = document.getElementById("cw-bluesky-section");
    const cwDiscordSection = document.getElementById("cw-discord-section");
    const counterMastodon = document.getElementById("counter-mastodon");
    const counterBluesky = document.getElementById("counter-bluesky");
    const counterDiscord = document.getElementById("counter-discord");
    const linkCardSection = document.getElementById("link-card-section");
    const linkUrl = document.getElementById("link-url");
    const btnPreviewLink = document.getElementById("btn-preview-link");
    const linkPreview = document.getElementById("link-preview");
    const imagesSection = document.getElementById("images-section");
    const imageInput = document.getElementById("image-input");
    const btnChooseImages = document.getElementById("btn-choose-images");
    const imagePreviews = document.getElementById("image-previews");
    const btnPost = document.getElementById("btn-post");
    const draftImageDataInput = document.getElementById("draft-image-data");
    const cbDraft = document.getElementById("cb-draft");

    // Mode elements
    const sharedTextSection = document.getElementById("shared-text-section");
    const platformTextsSection = document.getElementById("platform-texts-section");
    const previewSection = document.getElementById("preview-section");
    const textMastodon = document.getElementById("text-mastodon");
    const textBluesky = document.getElementById("text-bluesky");
    const textDiscord = document.getElementById("text-discord");
    const groupMastodon = document.getElementById("group-mastodon");
    const groupBluesky = document.getElementById("group-bluesky");
    const groupDiscord = document.getElementById("group-discord");
    const counterMastodonMode = document.getElementById("counter-mastodon-mode");
    const counterBlueskyMode = document.getElementById("counter-bluesky-mode");
    const counterDiscordMode = document.getElementById("counter-discord-mode");
    const btnShowPreview = document.getElementById("btn-show-preview");
    const previewPanels = document.getElementById("preview-panels");
    const previewMastodon = document.getElementById("preview-mastodon");
    const previewBluesky = document.getElementById("preview-bluesky");
    const previewDiscord = document.getElementById("preview-discord");
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const cbMirror = document.getElementById("cb-mirror");
    const mirrorLabel = document.getElementById("mirror-label");

    // Load modes config from embedded JSON
    let modesConfig = {};
    const modesConfigEl = document.getElementById("modes-config");
    if (modesConfigEl) {
        try {
            modesConfig = JSON.parse(modesConfigEl.textContent);
        } catch (e) {
            console.error("Failed to parse modes config:", e);
        }
    }

    // Track selected files via DataTransfer to allow individual removal
    let selectedFiles = new DataTransfer();

    // Track draft images (loaded from server) separately
    // Each: { draft_id, filename, alt_text, url }
    let draftImages = [];

    // Track whether a mode is currently active
    let activeMode = null;

    // Save original platform checkbox states for restore on deactivate
    let savedPlatformState = null;

    // --- Load draft images if present ---
    const draftImagesDataEl = document.getElementById("draft-images-data");
    const draftImagesIdEl = document.getElementById("draft-images-id");
    if (draftImagesDataEl && draftImagesIdEl) {
        const draftId = draftImagesIdEl.textContent.trim();
        try {
            const images = JSON.parse(draftImagesDataEl.textContent);
            draftImages = images.map(img => ({
                draft_id: draftId,
                filename: img.filename,
                alt_text: img.alt_text || "",
                url: `/draft-image/${draftId}/${img.filename}`,
            }));
        } catch (e) {
            console.error("Failed to parse draft images:", e);
        }
    }

    // --- Grapheme-aware character counting ---
    function countGraphemes(str) {
        if (typeof Intl !== "undefined" && Intl.Segmenter) {
            const segmenter = new Intl.Segmenter("en", { granularity: "grapheme" });
            return [...segmenter.segment(str)].length;
        }
        return [...str].length;
    }

    // --- Platform toggle ---
    function updatePlatformSections() {
        const mastodonChecked = cbMastodon.checked;
        const blueskyChecked = cbBluesky.checked;
        const discordChecked = cbDiscord.checked;

        cwMastodonSection.hidden = !mastodonChecked;
        cwBlueskySection.hidden = !blueskyChecked;
        cwDiscordSection.hidden = !discordChecked;

        if (activeMode) {
            // Show/hide per-platform textarea groups based on checkbox state
            groupMastodon.hidden = !mastodonChecked;
            groupBluesky.hidden = !blueskyChecked;
            groupDiscord.hidden = !discordChecked;
        } else {
            // Only show shared-text counters when no mode is active
            counterMastodon.hidden = !mastodonChecked;
            counterBluesky.hidden = !blueskyChecked;
            counterDiscord.hidden = !discordChecked;
            updateCharCounters();
        }
    }

    if (cbMastodon) cbMastodon.addEventListener("change", updatePlatformSections);
    if (cbBluesky) cbBluesky.addEventListener("change", updatePlatformSections);
    if (cbDiscord) cbDiscord.addEventListener("change", updatePlatformSections);
    // --- Character counters (shared textarea) ---
    function updateCharCounters() {
        const len = countGraphemes(textarea.value);

        if (!counterMastodon.hidden) {
            const countEl = counterMastodon.querySelector(".count");
            countEl.textContent = len;
            counterMastodon.classList.toggle("over-limit", len > 500);
        }

        if (!counterBluesky.hidden) {
            const countEl = counterBluesky.querySelector(".count");
            countEl.textContent = len;
            counterBluesky.classList.toggle("over-limit", len > 300);
        }

        if (!counterDiscord.hidden) {
            const countEl = counterDiscord.querySelector(".count");
            countEl.textContent = len;
            counterDiscord.classList.toggle("over-limit", len > 2000);
        }

    }

    textarea.addEventListener("input", updateCharCounters);

    // --- Per-platform character counters (mode textareas) ---
    function updateModeCharCounters() {
        const mastodonLen = countGraphemes(textMastodon.value);
        const mastodonCountEl = counterMastodonMode.querySelector(".count");
        mastodonCountEl.textContent = mastodonLen;
        counterMastodonMode.classList.toggle("over-limit", mastodonLen > 500);

        const blueskyLen = countGraphemes(textBluesky.value);
        const blueskyCountEl = counterBlueskyMode.querySelector(".count");
        blueskyCountEl.textContent = blueskyLen;
        counterBlueskyMode.classList.toggle("over-limit", blueskyLen > 300);

        const discordLen = countGraphemes(textDiscord.value);
        const discordCountEl = counterDiscordMode.querySelector(".count");
        discordCountEl.textContent = discordLen;
        counterDiscordMode.classList.toggle("over-limit", discordLen > 2000);

    }

    textMastodon.addEventListener("input", updateModeCharCounters);
    textBluesky.addEventListener("input", updateModeCharCounters);
    textDiscord.addEventListener("input", updateModeCharCounters);

    // --- Cross-sync platform textareas ---
    // When user types in one box, mirror the body (minus prefix/suffix) to the other
    let syncing = false;

    function getBody(text, prefix, suffix) {
        let body = text;
        if (prefix && body.startsWith(prefix)) {
            body = body.slice(prefix.length);
        }
        if (suffix && body.endsWith(suffix)) {
            body = body.slice(0, -suffix.length);
        }
        return body;
    }

    function syncFrom(source, target, sourcePrefix, sourceSuffix, targetPrefix, targetSuffix) {
        if (syncing || !activeMode) return;
        syncing = true;
        const body = getBody(source.value, sourcePrefix, sourceSuffix);
        target.value = (targetPrefix || "") + body + (targetSuffix || "");
        syncing = false;
        updateModeCharCounters();
    }

    function mirrorFromPlatform(sourcePlatform, sourceEl) {
        if (!activeMode || !cbMirror.checked) return;
        const mode = modesConfig[activeMode];
        if (!mode) return;
        const prefixes = mode.prefixes || {};
        const suffixes = mode.suffixes || {};
        const targets = {mastodon: textMastodon, bluesky: textBluesky, discord: textDiscord};
        for (const [platform, el] of Object.entries(targets)) {
            if (platform === sourcePlatform) continue;
            syncFrom(sourceEl, el,
                prefixes[sourcePlatform] || "", suffixes[sourcePlatform] || "",
                prefixes[platform] || "", suffixes[platform] || "");
        }
    }

    textMastodon.addEventListener("input", () => mirrorFromPlatform("mastodon", textMastodon));
    textBluesky.addEventListener("input", () => mirrorFromPlatform("bluesky", textBluesky));
    textDiscord.addEventListener("input", () => mirrorFromPlatform("discord", textDiscord));
    // --- Mode activation/deactivation ---
    function applyModeToTextarea(el, oldMode, newMode, platform) {
        const newPrefixes = newMode.prefixes || {};
        const newPre = newPrefixes[platform] || "";
        const newSuf = newMode.suffixes[platform] || "";

        // Always start fresh with the new mode's prefix/suffix
        el.value = newPre + newSuf;
        el.setSelectionRange(newPre.length, newPre.length);
    }

    function activateMode(name, skipTextareas) {
        const mode = modesConfig[name];
        if (!mode) return;

        const oldMode = activeMode ? modesConfig[activeMode] : null;
        activeMode = name;

        // Save current platform checkbox state (only on first activation)
        if (!savedPlatformState) {
            savedPlatformState = {
                mastodon: cbMastodon.checked,
                bluesky: cbBluesky.checked,
                discord: cbDiscord.checked,
            };
        }

        // Auto-check platforms specified by mode (but don't lock them)
        if (mode.platforms.includes("mastodon")) cbMastodon.checked = true;
        if (mode.platforms.includes("bluesky")) cbBluesky.checked = true;
        if (mode.platforms.includes("discord")) cbDiscord.checked = true;
        // Show per-platform textareas, hide shared
        sharedTextSection.hidden = true;
        platformTextsSection.hidden = false;
        previewSection.hidden = false;
        mirrorLabel.hidden = false;
        cbMirror.checked = false;

        // Apply prefix/suffix — strips old mode's, applies new mode's
        if (!skipTextareas) {
            applyModeToTextarea(textMastodon, oldMode, mode, "mastodon");
            applyModeToTextarea(textBluesky, oldMode, mode, "bluesky");
            applyModeToTextarea(textDiscord, oldMode, mode, "discord");
        }

        updatePlatformSections();
        updateModeCharCounters();
    }

    function deactivateMode() {
        activeMode = null;

        // Restore platform checkbox state
        if (savedPlatformState) {
            cbMastodon.checked = savedPlatformState.mastodon;
            cbBluesky.checked = savedPlatformState.bluesky;
            cbDiscord.checked = savedPlatformState.discord;
            savedPlatformState = null;
        }

        // Clear all textareas for a fresh start
        textarea.value = "";
        textMastodon.value = "";
        textBluesky.value = "";
        textDiscord.value = "";

        // Show shared textarea, hide per-platform
        sharedTextSection.hidden = false;
        platformTextsSection.hidden = true;
        previewSection.hidden = true;
        previewPanels.hidden = true;
        mirrorLabel.hidden = true;
        cbMirror.checked = false;

        updatePlatformSections();
    }

    // Mode radio change handler
    for (const radio of modeRadios) {
        radio.addEventListener("change", () => {
            if (radio.value) {
                activateMode(radio.value);
            } else {
                deactivateMode();
            }
        });
    }

    // --- Preview rendering ---
    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function highlightText(str) {
        let html = escapeHtml(str);
        // Highlight URLs
        html = html.replace(/(https?:\/\/[^\s<]+)/g, '<span class="highlight-url">$1</span>');
        // Highlight @mentions (handle Mastodon full-address @user@domain and simple @user)
        html = html.replace(/(^|[\s>])(@[\w.-]+(?:@[\w.-]+)?)/g, '$1<span class="highlight-mention">$2</span>');
        // Highlight #hashtags
        html = html.replace(/(^|[\s>])(#[\w]+)/g, '$1<span class="highlight-hashtag">$2</span>');
        // Preserve newlines
        html = html.replace(/\n/g, "<br>");
        return html;
    }

    if (btnShowPreview) {
        btnShowPreview.addEventListener("click", () => {
            previewMastodon.innerHTML = highlightText(textMastodon.value);
            previewMastodon.parentElement.hidden = !cbMastodon.checked;
            previewBluesky.innerHTML = highlightText(textBluesky.value);
            previewBluesky.parentElement.hidden = !cbBluesky.checked;
            previewDiscord.innerHTML = highlightText(textDiscord.value);
            previewDiscord.parentElement.hidden = !cbDiscord.checked;
            previewPanels.hidden = false;
        });
    }

    // --- Total image count (newly selected + draft) ---
    function totalImageCount() {
        return selectedFiles.files.length + draftImages.length;
    }

    // --- Mutual exclusivity: images vs link card ---
    function updateMutualExclusivity() {
        const hasImages = totalImageCount() > 0;
        const hasLink = linkUrl.value.trim() !== "";

        if (hasImages) {
            linkCardSection.setAttribute("disabled", "");
            linkUrl.disabled = true;
            btnPreviewLink.disabled = true;
        } else {
            linkCardSection.removeAttribute("disabled");
            linkUrl.disabled = false;
            btnPreviewLink.disabled = false;
        }

        if (hasLink) {
            imagesSection.setAttribute("disabled", "");
            imageInput.disabled = true;
            btnChooseImages.disabled = true;
        } else {
            imagesSection.removeAttribute("disabled");
            imageInput.disabled = false;
            btnChooseImages.disabled = false;
        }
    }

    linkUrl.addEventListener("input", updateMutualExclusivity);

    // --- Image selection and previews ---
    btnChooseImages.addEventListener("click", () => {
        imageInput.click();
    });

    imageInput.addEventListener("change", () => {
        const newFiles = imageInput.files;
        for (let i = 0; i < newFiles.length; i++) {
            if (totalImageCount() + i >= 4) break;
            if (selectedFiles.files.length >= 4 - draftImages.length) break;
            selectedFiles.items.add(newFiles[i]);
        }
        imageInput.value = "";
        renderImagePreviews();
        updateMutualExclusivity();
    });

    function renderImagePreviews() {
        imagePreviews.innerHTML = "";

        // Render draft images first (alt text tracked in draftImages array, not form fields)
        for (let i = 0; i < draftImages.length; i++) {
            const di = draftImages[i];
            const item = document.createElement("div");
            item.className = "image-preview-item";

            const img = document.createElement("img");
            img.src = di.url;
            img.alt = "Draft image preview";
            item.appendChild(img);

            const altInput = document.createElement("input");
            altInput.type = "text";
            altInput.className = "draft-alt-text";
            altInput.dataset.draftIndex = i;
            altInput.placeholder = "Alt text";
            altInput.value = di.alt_text;
            altInput.addEventListener("input", () => {
                draftImages[i].alt_text = altInput.value;
            });
            item.appendChild(altInput);

            const btnRemove = document.createElement("button");
            btnRemove.type = "button";
            btnRemove.className = "btn-remove";
            btnRemove.textContent = "\u00d7";
            btnRemove.addEventListener("click", () => {
                removeDraftImage(i);
            });
            item.appendChild(btnRemove);

            imagePreviews.appendChild(item);
        }

        // Render newly selected files (alt_text_0, alt_text_1, ... independent of draft images)
        const files = selectedFiles.files;
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const item = document.createElement("div");
            item.className = "image-preview-item";

            const img = document.createElement("img");
            img.src = URL.createObjectURL(file);
            img.alt = "Preview";
            item.appendChild(img);

            const altInput = document.createElement("input");
            altInput.type = "text";
            altInput.name = `alt_text_${i}`;
            altInput.placeholder = "Alt text";
            item.appendChild(altInput);

            const btnRemove = document.createElement("button");
            btnRemove.type = "button";
            btnRemove.className = "btn-remove";
            btnRemove.textContent = "\u00d7";
            btnRemove.addEventListener("click", () => {
                removeFile(i);
            });
            item.appendChild(btnRemove);

            imagePreviews.appendChild(item);
        }

        // Update the button text
        const total = totalImageCount();
        if (total > 0) {
            btnChooseImages.textContent = `Choose Images (${total}/4)`;
        } else {
            btnChooseImages.textContent = "Choose Images";
        }

        if (total >= 4) {
            btnChooseImages.disabled = true;
        }
    }

    function removeFile(index) {
        const dt = new DataTransfer();
        const files = selectedFiles.files;
        for (let i = 0; i < files.length; i++) {
            if (i !== index) dt.items.add(files[i]);
        }
        selectedFiles = dt;
        renderImagePreviews();
        updateMutualExclusivity();
    }

    function removeDraftImage(index) {
        draftImages.splice(index, 1);
        renderImagePreviews();
        updateMutualExclusivity();
    }

    // --- Link preview ---
    btnPreviewLink.addEventListener("click", async () => {
        const url = linkUrl.value.trim();
        if (!url) return;

        btnPreviewLink.setAttribute("aria-busy", "true");
        btnPreviewLink.textContent = "Loading...";

        try {
            const resp = await fetch("/link-preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url }),
            });
            const data = await resp.json();

            if (data.title || data.description) {
                document.getElementById("link-preview-title").textContent = data.title || "";
                document.getElementById("link-preview-desc").textContent = data.description || "";
                const previewImg = document.getElementById("link-preview-img");
                if (data.image_url) {
                    previewImg.src = data.image_url;
                    previewImg.hidden = false;
                } else {
                    previewImg.hidden = true;
                }
                linkPreview.hidden = false;
            } else {
                linkPreview.hidden = true;
            }
        } catch (err) {
            console.error("Link preview failed:", err);
            linkPreview.hidden = true;
        }

        btnPreviewLink.removeAttribute("aria-busy");
        btnPreviewLink.textContent = "Preview";
    });

    // --- Form submission: attach files from DataTransfer ---
    form.addEventListener("submit", (e) => {
        const isDraft = cbDraft.checked;

        // Skip platform validation for drafts
        if (!isDraft) {
            if (!cbMastodon.checked && !cbBluesky.checked && !cbDiscord.checked) {
                e.preventDefault();
                alert("Please select at least one platform.");
                return;
            }
        }

        // Validate text: when mode active, check per-platform; otherwise check shared
        if (activeMode) {
            if (!textMastodon.value.trim() && !textBluesky.value.trim() && !textDiscord.value.trim()) {
                e.preventDefault();
                alert("Please enter text for at least one platform.");
                return;
            }
            // Disable shared textarea so it doesn't submit
            textarea.disabled = true;
        } else {
            if (!textarea.value.trim()) {
                e.preventDefault();
                alert("Please enter some text.");
                return;
            }
            // Disable per-platform fields so they don't submit
            textMastodon.disabled = true;
            textBluesky.disabled = true;
            textDiscord.disabled = true;
        }

        // Validate: alt text is filled for all images
        if (totalImageCount() > 0) {
            // Check draft images
            for (const di of draftImages) {
                if (!di.alt_text.trim()) {
                    e.preventDefault();
                    alert("Please provide alt text for all images.");
                    return;
                }
            }
            // Check newly selected file alt texts
            const files = selectedFiles.files;
            for (let i = 0; i < files.length; i++) {
                const altInput = imagePreviews.querySelector(`input[name="alt_text_${i}"]`);
                if (altInput && !altInput.value.trim()) {
                    e.preventDefault();
                    alert("Please provide alt text for all images.");
                    return;
                }
            }
        }

        // Serialize draft images into hidden input
        if (draftImages.length > 0) {
            // Update alt texts from current input values
            const data = draftImages.map(di => ({
                draft_id: di.draft_id,
                filename: di.filename,
                alt_text: di.alt_text,
            }));
            draftImageDataInput.value = JSON.stringify(data);
        } else {
            draftImageDataInput.value = "";
        }

        // Attach selected files to a hidden input
        const dt = selectedFiles;
        if (dt.files.length > 0) {
            const hiddenInput = document.createElement("input");
            hiddenInput.type = "file";
            hiddenInput.name = "images";
            hiddenInput.multiple = true;
            hiddenInput.hidden = true;
            hiddenInput.files = dt.files;
            form.appendChild(hiddenInput);
        }

        btnPost.setAttribute("aria-busy", "true");
        btnPost.textContent = isDraft ? "Saving..." : "Posting...";
    });

    // --- Draft restoration: if draft has a mode, activate it ---
    const checkedMode = document.querySelector('input[name="mode"]:checked');
    if (checkedMode && checkedMode.value) {
        // Activate mode without overwriting pre-populated textarea values
        activateMode(checkedMode.value, true);
    }

    // --- Clear button ---
    document.getElementById("btn-clear").addEventListener("click", () => {
        // Deactivate mode if active
        if (activeMode) {
            const noneRadio = document.getElementById("mode-none");
            if (noneRadio) noneRadio.checked = true;
            deactivateMode();
        }

        // Clear text fields
        textarea.value = "";
        textMastodon.value = "";
        textBluesky.value = "";
        textDiscord.value = "";
        linkUrl.value = "";
        linkPreview.hidden = true;

        // Uncheck platforms
        cbMastodon.checked = false;
        cbBluesky.checked = false;
        cbDiscord.checked = false;

        // Reset content warnings
        document.querySelectorAll('input[name="cw_mastodon"][value=""]').forEach(r => r.checked = true);
        document.querySelectorAll('input[name="cw_bluesky"][value=""]').forEach(r => r.checked = true);
        document.querySelectorAll('input[name="cw_discord"][value=""]').forEach(r => r.checked = true);

        // Clear images
        selectedFiles = new DataTransfer();
        draftImages = [];
        renderImagePreviews();

        // Clear BWE hidden fields
        document.getElementById("bwe-site-name").value = "";
        document.getElementById("bwe-site-url").value = "";

        // Reset draft checkbox
        cbDraft.checked = true;

        updatePlatformSections();
        updateCharCounters();
        updateMutualExclusivity();
    });

    // --- Fetch social links and append @-mentions to per-platform textareas ---
    async function fetchAndAppendSocialLinks(siteUrl) {
        try {
            const resp = await fetch("/social-links", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: siteUrl }),
            });
            if (!resp.ok) return;
            const data = await resp.json();

            for (const [platform, el] of [["mastodon", textMastodon], ["bluesky", textBluesky]]) {
                const mention = data[platform];
                if (!mention) continue;
                // Only append if mention isn't already in the textarea
                if (el.value.includes(mention)) continue;
                // Append mention after existing content with a space
                el.value = el.value.trimEnd() + " " + mention;
            }
            updateModeCharCounters();
        } catch (err) {
            console.error("Social links fetch failed:", err);
        }
    }

    // --- BWE Post buttons: populate form from sidebar ---
    document.querySelectorAll(".btn-bwe-post").forEach(btn => {
        btn.addEventListener("click", () => {
            const name = btn.dataset.name;
            const url = btn.dataset.url;

            // Read M/B/D checkboxes from the BWE queue item
            const queueItem = btn.closest(".bwe-queue-item");
            const platCbs = queueItem ? queueItem.querySelectorAll(".bwe-plat-cb") : [];
            const platformMap = {M: cbMastodon, B: cbBluesky, D: cbDiscord};
            const checkedPlatforms = [];

            // Set main platform checkboxes from BWE entry's selections
            cbMastodon.checked = false;
            cbBluesky.checked = false;
            cbDiscord.checked = false;
            platCbs.forEach(cb => {
                const mainCb = platformMap[cb.dataset.platform];
                if (mainCb && cb.checked) {
                    mainCb.checked = true;
                    checkedPlatforms.push(cb.dataset.platform);
                }
            });

            // Select and activate 11ty-bwe mode
            const bweRadio = document.getElementById("mode-11ty-bwe");
            if (bweRadio) {
                bweRadio.checked = true;
                activateMode("11ty-bwe");
            }

            // Override platform checkboxes after mode activation (mode may auto-check)
            cbMastodon.checked = checkedPlatforms.includes("M");
            cbBluesky.checked = checkedPlatforms.includes("B");
            cbDiscord.checked = checkedPlatforms.includes("D");

            // Insert site name into per-platform textareas after the prefix
            const mode = modesConfig["11ty-bwe"];
            if (mode) {
                const prefixes = mode.prefixes || {};
                const suffixes = mode.suffixes || {};
                const textareaMap = {mastodon: textMastodon, bluesky: textBluesky, discord: textDiscord};
                for (const [platform, el] of Object.entries(textareaMap)) {
                    const pre = prefixes[platform] || "";
                    const suf = suffixes[platform] || "";
                    el.value = pre + name + suf;
                }
                updateModeCharCounters();
            }

            // Update visibility of platform groups
            updatePlatformSections();

            // Set link URL
            linkUrl.value = url;

            // Populate hidden fields
            document.getElementById("bwe-site-name").value = name;
            document.getElementById("bwe-site-url").value = url;

            // Trigger mutual exclusivity (link URL disables images)
            updateMutualExclusivity();

            // Scroll to top of form
            form.scrollIntoView({ behavior: "smooth" });

            // Fetch social links and append @-mentions (async, non-blocking)
            fetchAndAppendSocialLinks(url);
        });
    });

    // Initialize
    updatePlatformSections();
    if (draftImages.length > 0) {
        renderImagePreviews();
        updateMutualExclusivity();
    }

    // Fetch social links on page load for Use/draft BWE entries
    const bweSiteUrlField = document.getElementById("bwe-site-url");
    if (bweSiteUrlField && bweSiteUrlField.value.trim() && activeMode === "11ty-bwe") {
        fetchAndAppendSocialLinks(bweSiteUrlField.value.trim());
    }

    // Create / Delete / Edit Blog Post buttons
    const btnCreatePost = document.getElementById("btn-create-post");
    const btnDeletePost = document.getElementById("btn-delete-post");
    const btnEditPost = document.getElementById("btn-edit-post");

    if (btnCreatePost) {
        btnCreatePost.addEventListener("click", async () => {
            const issueNumber = btnCreatePost.dataset.issue;
            const today = new Date().toISOString().split("T")[0];
            btnCreatePost.disabled = true;
            btnCreatePost.textContent = "Creating...";
            try {
                const resp = await fetch("/create-blog-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ issue_number: issueNumber, date: today }),
                });
                const data = await resp.json();
                if (data.success) {
                    btnCreatePost.hidden = true;
                    btnCreatePost.textContent = "New Bundle Issue";
                    btnCreatePost.disabled = false;
                    if (btnDeletePost) btnDeletePost.hidden = false;
                    if (btnEditPost) btnEditPost.hidden = false;
                } else {
                    btnCreatePost.textContent = data.error || "Error";
                    setTimeout(() => { btnCreatePost.textContent = "New Bundle Issue"; btnCreatePost.disabled = false; }, 3000);
                }
            } catch {
                btnCreatePost.textContent = "Error";
                setTimeout(() => { btnCreatePost.textContent = "New Bundle Issue"; btnCreatePost.disabled = false; }, 3000);
            }
        });
    }

    if (btnDeletePost) {
        btnDeletePost.addEventListener("click", async () => {
            const issueNumber = btnDeletePost.dataset.issue;
            const padded = String(issueNumber).padStart(2, "0");
            if (!confirm(`Are you sure you want to delete 11ty-bundle-${padded}.md file?`)) return;
            btnDeletePost.disabled = true;
            try {
                const resp = await fetch("/delete-blog-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ issue_number: issueNumber }),
                });
                const data = await resp.json();
                if (data.success) {
                    btnDeletePost.hidden = true;
                    btnDeletePost.disabled = false;
                    if (btnEditPost) btnEditPost.hidden = true;
                    if (btnCreatePost) btnCreatePost.hidden = false;
                } else {
                    btnDeletePost.disabled = false;
                }
            } catch {
                btnDeletePost.disabled = false;
            }
        });
    }

    if (btnEditPost) {
        btnEditPost.addEventListener("click", async () => {
            const issueNumber = btnEditPost.dataset.issue;
            try {
                await fetch("/edit-blog-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ issue_number: issueNumber }),
                });
            } catch { /* ignore */ }
        });
    }
});
