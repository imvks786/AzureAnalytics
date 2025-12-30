
let selectedSiteId = localStorage.getItem('selectedSiteId') || null;

function initSiteSelector() {
    const btn = document.getElementById('siteButton');
    const dropdown = document.getElementById('siteDropdown');
    if (!btn || !dropdown) return;

    // open/close toggle
    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        dropdown.classList.toggle('open');
    });

    // item click
    dropdown.querySelectorAll('.site-item').forEach(item => {
        item.addEventListener('click', function () {
            const siteId = this.getAttribute('data-site-id');
            const name = this.querySelector('.site-item-name')?.textContent || siteId;
            // set selection (empty siteId means "All sites")
            if (!siteId) {
                selectedSiteId = null;
                localStorage.removeItem('selectedSiteId');
            } else {
                selectedSiteId = siteId;
                localStorage.setItem('selectedSiteId', siteId);
            }
            document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
            dropdown.classList.remove('open');

            // Trigger a custom event so dashboard can listen and refresh
            const event = new CustomEvent('siteChanged', { detail: { siteId: selectedSiteId } });
            document.dispatchEvent(event);

            // For backward compatibility if existing code calls functions directly
            if (typeof fetchRealtime === 'function') fetchRealtime();
            if (typeof fetchEventCounts === 'function') fetchEventCounts();
        });
    });

    // click outside to close
    document.addEventListener('click', function () {
        dropdown.classList.remove('open');
    });

    // set initial text
    const items = dropdown.querySelectorAll('.site-item');
    if (!selectedSiteId && items.length) {
        // default to first (prefer "All sites" if present)
        const first = items[0];
        const firstId = first.getAttribute('data-site-id');
        if (!firstId) {
            selectedSiteId = null;
            localStorage.removeItem('selectedSiteId');
        } else {
            selectedSiteId = firstId;
            localStorage.setItem('selectedSiteId', selectedSiteId);
        }
        const name = first.querySelector('.site-item-name')?.textContent || (selectedSiteId || 'All sites');
        document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
    } else if (selectedSiteId) {
        const selectedEl = dropdown.querySelector(`.site-item[data-site-id="${selectedSiteId}"]`);
        if (selectedEl) {
            const name = selectedEl.querySelector('.site-item-name')?.textContent || selectedSiteId;
            document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
        }
    } else if (!selectedSiteId && items.length) {
        // fallback to all sites label
        document.getElementById('siteButton').innerHTML = `All sites <span class="caret">▾</span>`;
    }
}

// Profile dropdown init
function initProfileDropdown() {
    const profile = document.getElementById('userProfile');
    if (!profile) return;

    profile.addEventListener('click', function (e) {
        e.stopPropagation();
        this.classList.toggle('open');
        const isOpen = this.classList.contains('open');
        this.setAttribute('aria-expanded', isOpen);
    });

    // Close when clicking outside
    document.addEventListener('click', function () {
        profile.classList.remove('open');
        profile.setAttribute('aria-expanded', 'false');
    });
}

// Init when loaded
window.addEventListener('DOMContentLoaded', function () {
    initSiteSelector();
    initProfileDropdown();
});
