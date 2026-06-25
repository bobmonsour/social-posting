(function() {
    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function renderCommits(commits, containerId) {
        var container = document.getElementById(containerId);
        if (!commits || commits.length === 0) {
            container.textContent = 'No commits found.';
            return;
        }
        var html = '';
        for (var i = 0; i < commits.length; i++) {
            var c = commits[i];
            html += '<div class="dbmgmt-commit">';
            html += '<div class="dbmgmt-commit-header">';
            html += '<a href="' + escapeHtml(c.url) + '" target="_blank" rel="noopener">' + escapeHtml(c.sha) + '</a>';
            html += '<span>' + escapeHtml(c.date) + '</span>';
            html += '</div>';
            if (c.added && c.added.length > 0) {
                html += '<ul>';
                for (var j = 0; j < c.added.length; j++) {
                    html += '<li>' + escapeHtml(c.added[j]) + '</li>';
                }
                html += '</ul>';
            } else {
                html += '<p class="dbmgmt-no-entries">No entries added</p>';
            }
            html += '</div>';
        }
        container.innerHTML = html;
    }

    fetch('/db-mgmt/commits')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            renderCommits(data.bundledb, 'bundledb-commits');
            renderCommits(data.showcase, 'showcase-commits');
        })
        .catch(function() {
            document.getElementById('bundledb-commits').textContent = 'Failed to load commits.';
            document.getElementById('showcase-commits').textContent = 'Failed to load commits.';
        });

    // ===== SveltiaCMS Check =====
    var sveltiacmsSites = [];
    var deletedIndices = {};
    var btnCheck = document.getElementById('btn-sveltiacms-check');
    var modal = document.getElementById('sveltiacms-modal');
    var siteList = document.getElementById('sveltiacms-site-list');
    var selectAll = document.getElementById('sveltiacms-select-all');
    var btnCancel = document.getElementById('sveltiacms-cancel');
    var btnSave = document.getElementById('sveltiacms-save');

    if (btnCheck) {
        btnCheck.addEventListener('click', function() {
            btnCheck.disabled = true;
            btnCheck.textContent = 'Checking...';

            fetch('/db-mgmt/sveltiacms-check', { method: 'POST' })
                .then(function(res) { return res.json().then(function(data) { return { ok: res.ok, data: data }; }); })
                .then(function(result) {
                    if (!result.ok) {
                        showInlineMessage(result.data.error || 'Check failed', true);
                        return;
                    }
                    sveltiacmsSites = result.data.sites || [];
                    if (sveltiacmsSites.length === 0) {
                        showInlineMessage('No new Eleventy sites found', false);
                        return;
                    }
                    renderSiteList();
                    selectAll.checked = true;
                    modal.style.display = 'flex';
                })
                .catch(function(err) {
                    showInlineMessage('Error: ' + err.message, true);
                })
                .finally(function() {
                    btnCheck.disabled = false;
                    btnCheck.textContent = 'Check SveltiaCMS';
                });
        });
    }

    function showInlineMessage(msg, isError) {
        var existing = document.getElementById('sveltiacms-inline-msg');
        if (existing) existing.remove();
        var el = document.createElement('span');
        el.id = 'sveltiacms-inline-msg';
        el.style.marginLeft = '0.75rem';
        el.style.fontSize = '0.85rem';
        el.style.fontWeight = '600';
        el.style.color = isError ? '#c62828' : 'var(--pico-muted-color)';
        el.textContent = msg;
        btnCheck.parentNode.appendChild(el);
        setTimeout(function() { el.remove(); }, 5000);
    }

    function renderSiteList() {
        deletedIndices = {};
        var html = '';
        for (var i = 0; i < sveltiacmsSites.length; i++) {
            var site = sveltiacmsSites[i];
            html += '<div class="sveltiacms-site-row" data-row="' + i + '" style="display: flex; align-items: flex-start; gap: 0.5rem;">';
            html += '<label style="display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0; cursor: pointer; flex: 1;">';
            html += '<input type="checkbox" class="sveltiacms-cb" data-index="' + i + '" checked style="margin: 0.2rem 0 0 0; flex-shrink: 0;">';
            html += '<span>';
            html += '<a href="' + escapeHtml(site.url) + '" target="_blank" rel="noopener" style="font-weight: 600;">' + escapeHtml(site.name) + '</a>';
            if (site.description) {
                html += '<br><span style="font-size: 0.85rem; color: var(--pico-muted-color);">' + escapeHtml(site.description) + '</span>';
            }
            html += '</span>';
            html += '</label>';
            html += '<button type="button" class="sveltiacms-delete" data-index="' + i + '" title="Delete &mdash; won\'t reappear on future checks" style="flex-shrink: 0; background: none; border: none; color: #c62828; cursor: pointer; font-size: 1.2rem; line-height: 1; padding: 0 0.3rem; width: auto; margin: 0;">&times;</button>';
            html += '</div>';
        }
        siteList.innerHTML = html;

        var dels = siteList.querySelectorAll('.sveltiacms-delete');
        for (var j = 0; j < dels.length; j++) {
            dels[j].addEventListener('click', function() {
                var idx = parseInt(this.dataset.index);
                deletedIndices[idx] = true;
                var row = siteList.querySelector('.sveltiacms-site-row[data-row="' + idx + '"]');
                if (row) { row.remove(); }
            });
        }
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            var cbs = siteList.querySelectorAll('.sveltiacms-cb');
            for (var i = 0; i < cbs.length; i++) {
                cbs[i].checked = selectAll.checked;
            }
        });
    }

    if (btnCancel) {
        btnCancel.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }

    if (btnSave) {
        btnSave.addEventListener('click', function() {
            var selected = [];
            var skipped = [];
            for (var i = 0; i < sveltiacmsSites.length; i++) {
                var site = sveltiacmsSites[i];
                if (deletedIndices[i]) {
                    // Deleted: keep only a lightweight skip record so it
                    // never reappears on a future check.
                    skipped.push({ url: site.url, skip: true });
                    continue;
                }
                var cb = siteList.querySelector('.sveltiacms-cb[data-index="' + i + '"]');
                if (cb && cb.checked) {
                    selected.push(site);
                } else {
                    skipped.push(Object.assign({}, site, { skip: true }));
                }
            }
            if (selected.length === 0 && skipped.length === 0) {
                modal.style.display = 'none';
                return;
            }

            btnSave.disabled = true;
            btnSave.textContent = 'Saving...';

            fetch('/db-mgmt/sveltiacms-save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sites: selected.concat(skipped) })
            })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.ok) {
                        window.location.reload();
                    } else {
                        showInlineMessage('Save failed: ' + (data.error || 'Unknown error'), true);
                        modal.style.display = 'none';
                    }
                })
                .catch(function(err) {
                    showInlineMessage('Save failed: ' + err.message, true);
                    modal.style.display = 'none';
                })
                .finally(function() {
                    btnSave.disabled = false;
                    btnSave.textContent = 'Save Sites';
                });
        });
    }
})();
