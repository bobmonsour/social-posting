document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("compose-form");
    const textarea = document.getElementById("post-text");
    const cbMastodon = document.getElementById("cb-mastodon");
    const cbBluesky = document.getElementById("cb-bluesky");
    const cwMastodonSection = document.getElementById("cw-mastodon-section");
    const cwBlueskySection = document.getElementById("cw-bluesky-section");
    const counterMastodon = document.getElementById("counter-mastodon");
    const counterBluesky = document.getElementById("counter-bluesky");
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
    const counterMastodonMode = document.getElementById("counter-mastodon-mode");
    const counterBlueskyMode = document.getElementById("counter-bluesky-mode");
    const btnShowPreview = document.getElementById("btn-show-preview");
    const previewPanels = document.getElementById("preview-panels");
    const previewMastodon = document.getElementById("preview-mastodon");
    const previewBluesky = document.getElementById("preview-bluesky");
    const modeRadios = document.querySelectorAll('input[name="mode"]');

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

        cwMastodonSection.hidden = !mastodonChecked;
        cwBlueskySection.hidden = !blueskyChecked;

        // Only show shared-text counters when no mode is active
        if (!activeMode) {
            counterMastodon.hidden = !mastodonChecked;
            counterBluesky.hidden = !blueskyChecked;
            updateCharCounters();
        }
    }

    if (cbMastodon) cbMastodon.addEventListener("change", updatePlatformSections);
    if (cbBluesky) cbBluesky.addEventListener("change", updatePlatformSections);

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
    }

    textMastodon.addEventListener("input", updateModeCharCounters);
    textBluesky.addEventListener("input", updateModeCharCounters);

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

    textMastodon.addEventListener("input", () => {
        if (!activeMode) return;
        const mode = modesConfig[activeMode];
        if (!mode) return;
        const prefixes = mode.prefixes || {};
        syncFrom(textMastodon, textBluesky,
            prefixes.mastodon || "", mode.suffixes.mastodon || "",
            prefixes.bluesky || "", mode.suffixes.bluesky || "");
    });

    textBluesky.addEventListener("input", () => {
        if (!activeMode) return;
        const mode = modesConfig[activeMode];
        if (!mode) return;
        const prefixes = mode.prefixes || {};
        syncFrom(textBluesky, textMastodon,
            prefixes.bluesky || "", mode.suffixes.bluesky || "",
            prefixes.mastodon || "", mode.suffixes.mastodon || "");
    });

    // --- Mode activation/deactivation ---
    function applyModeToTextarea(el, oldMode, newMode, platform) {
        const oldPrefixes = oldMode ? (oldMode.prefixes || {}) : {};
        const oldPre = oldPrefixes[platform] || "";
        const oldSuf = oldMode ? (oldMode.suffixes[platform] || "") : "";
        const newPrefixes = newMode.prefixes || {};
        const newPre = newPrefixes[platform] || "";
        const newSuf = newMode.suffixes[platform] || "";

        if (!el.value.trim()) {
            // Empty textarea — just pre-fill
            el.value = newPre + newSuf;
        } else {
            // Extract body from old mode's prefix/suffix, apply new ones
            const body = getBody(el.value, oldPre, oldSuf);
            el.value = newPre + body + newSuf;
        }
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
                mastodonDisabled: cbMastodon.disabled,
                blueskyDisabled: cbBluesky.disabled,
            };
        }

        // Auto-check and lock platforms specified by mode
        if (mode.platforms.includes("mastodon")) {
            cbMastodon.checked = true;
            cbMastodon.disabled = true;
        }
        if (mode.platforms.includes("bluesky")) {
            cbBluesky.checked = true;
            cbBluesky.disabled = true;
        }

        // Show per-platform textareas, hide shared
        sharedTextSection.hidden = true;
        platformTextsSection.hidden = false;
        previewSection.hidden = false;

        // Apply prefix/suffix — strips old mode's, applies new mode's
        if (!skipTextareas) {
            applyModeToTextarea(textMastodon, oldMode, mode, "mastodon");
            applyModeToTextarea(textBluesky, oldMode, mode, "bluesky");
        }

        updatePlatformSections();
        updateModeCharCounters();
    }

    function deactivateMode() {
        activeMode = null;

        // Restore platform checkbox state
        if (savedPlatformState) {
            cbMastodon.checked = savedPlatformState.mastodon;
            cbMastodon.disabled = savedPlatformState.mastodonDisabled;
            cbBluesky.checked = savedPlatformState.bluesky;
            cbBluesky.disabled = savedPlatformState.blueskyDisabled;
            savedPlatformState = null;
        }

        // Show shared textarea, hide per-platform
        sharedTextSection.hidden = false;
        platformTextsSection.hidden = true;
        previewSection.hidden = true;
        previewPanels.hidden = true;

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
            previewBluesky.innerHTML = highlightText(textBluesky.value);
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
            if (!cbMastodon.checked && !cbBluesky.checked) {
                e.preventDefault();
                alert("Please select at least one platform.");
                return;
            }
        }

        // Validate text: when mode active, check per-platform; otherwise check shared
        if (activeMode) {
            if (!textMastodon.value.trim() && !textBluesky.value.trim()) {
                e.preventDefault();
                alert("Please enter text for at least one platform.");
                return;
            }
            // Disable shared textarea so it doesn't submit
            textarea.disabled = true;
            // Re-enable platform checkboxes so their values submit (mode had disabled them)
            cbMastodon.disabled = false;
            cbBluesky.disabled = false;
        } else {
            if (!textarea.value.trim()) {
                e.preventDefault();
                alert("Please enter some text.");
                return;
            }
            // Disable per-platform fields so they don't submit
            textMastodon.disabled = true;
            textBluesky.disabled = true;
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
        linkUrl.value = "";
        linkPreview.hidden = true;

        // Uncheck platforms
        cbMastodon.checked = false;
        cbBluesky.checked = false;

        // Reset content warnings
        document.querySelectorAll('input[name="cw_mastodon"][value=""]').forEach(r => r.checked = true);
        document.querySelectorAll('input[name="cw_bluesky"][value=""]').forEach(r => r.checked = true);

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

    // --- BWE Post buttons: populate form from sidebar ---
    document.querySelectorAll(".btn-bwe-post").forEach(btn => {
        btn.addEventListener("click", () => {
            const name = btn.dataset.name;
            const url = btn.dataset.url;

            // Check both platforms
            cbMastodon.checked = true;
            cbBluesky.checked = true;

            // Select and activate 11ty-bwe mode
            const bweRadio = document.getElementById("mode-11ty-bwe");
            if (bweRadio) {
                bweRadio.checked = true;
                activateMode("11ty-bwe");
            }

            // Insert site name into both textareas after the prefix
            const mode = modesConfig["11ty-bwe"];
            if (mode) {
                const prefixes = mode.prefixes || {};
                const suffixes = mode.suffixes || {};
                for (const [platform, el] of [["mastodon", textMastodon], ["bluesky", textBluesky]]) {
                    const pre = prefixes[platform] || "";
                    const suf = suffixes[platform] || "";
                    el.value = pre + name + suf;
                }
                updateModeCharCounters();
            }

            // Set link URL
            linkUrl.value = url;

            // Populate hidden fields
            document.getElementById("bwe-site-name").value = name;
            document.getElementById("bwe-site-url").value = url;

            // Trigger mutual exclusivity (link URL disables images)
            updateMutualExclusivity();

            // Scroll to top of form
            form.scrollIntoView({ behavior: "smooth" });
        });
    });

    // Initialize
    updatePlatformSections();
    if (draftImages.length > 0) {
        renderImagePreviews();
        updateMutualExclusivity();
    }
});
