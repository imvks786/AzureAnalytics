
// Sidebar toggle init and persistence
function initSidebarToggle() {
    const btn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (!btn || !sidebar) return;

    // restore state (desktop only)
    if (window.innerWidth > 880) {
        const collapsed = localStorage.getItem('sidebarCollapsed') === '1';
        if (collapsed) sidebar.classList.add('collapsed');
    }

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();

        if (window.innerWidth <= 880) {
            // Mobile behavior: toggle 'open' class
            sidebar.classList.toggle('open');
            if (overlay) {
                overlay.classList.toggle('active', sidebar.classList.contains('open'));
            }
        } else {
            // Desktop behavior: toggle 'collapsed' class
            sidebar.classList.toggle('collapsed');
            // persist
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0');
        }
    });

    // Close when clicking overlay (mobile)
    if (overlay) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // Close when clicking a nav item on mobile
    const navItems = sidebar.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', function () {
            if (window.innerWidth <= 880) {
                sidebar.classList.remove('open');
                if (overlay) overlay.classList.remove('active');
            }
        });
    });

    // Handle resize events to cleanup classes
    window.addEventListener('resize', function () {
        if (window.innerWidth > 880) {
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('active');

            // Restore persistent state for desktop
            const collapsed = localStorage.getItem('sidebarCollapsed') === '1';
            if (collapsed) {
                sidebar.classList.add('collapsed');
            } else {
                sidebar.classList.remove('collapsed');
            }
        }
    });
}

window.addEventListener('DOMContentLoaded', function () {
    initSidebarToggle();
});

// Dropdown handling for sidebar groups
window.addEventListener('DOMContentLoaded', function () {
    const dropdownToggles = document.querySelectorAll('[data-dropdown]');
    dropdownToggles.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const parent = btn.closest('.nav-dropdown');
            if (!parent) return;
            parent.classList.toggle('open');
        });
    });
});
