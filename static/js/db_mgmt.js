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
})();
