// ==========================================
// SPA State Management
// ==========================================
const state = {
    user: null, // Logged in user info
    currentPage: 'overview',
    activeChatPhone: null,
    chatPollInterval: null,
    recentRegistrationsPoll: null,
    chatsList: [],
    activeChatMessages: [],
    lastMessageTime: null,

    locations: []
};

const BASE_URL = '/api/admin';

// Utility: debounce for search inputs
function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// Utility: HTML Escape
function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g,
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

// Utility: Relative time formatter
function formatRelativeTime(dateString) {
    if (!dateString) return '';
    try {
        const cleanDateStr = dateString.replace(' ', 'T');
        const date = new Date(cleanDateStr);
        if (isNaN(date.getTime())) return dateString;

        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;

        const diffHrs = Math.floor(diffMins / 60);
        if (diffHrs < 24) return `${diffHrs}h ago`;

        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return dateString;
    }
}

// Utility: UI Loaders
function showPageLoading() {
    const bar = document.getElementById('top-progress-bar');
    if (bar) {
        bar.classList.remove('done');
        bar.classList.add('loading');
    }
}
function hidePageLoading() {
    const bar = document.getElementById('top-progress-bar');
    if (bar) {
        bar.classList.remove('loading');
        bar.classList.add('done');
        setTimeout(() => bar.classList.remove('done'), 800);
    }
}
function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    if (isLoading) {
        btn.classList.add('loading');
        if (!btn.hasAttribute('data-original-html')) {
            btn.setAttribute('data-original-html', btn.innerHTML);
        }
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...';
    } else {
        btn.classList.remove('loading');
        if (btn.hasAttribute('data-original-html')) {
            btn.innerHTML = btn.getAttribute('data-original-html');
        }
    }
}

// ==========================================
// Initialization & Authentication Checked
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    checkAuthentication();
    setupEventListeners();
    startClock();
});

function startClock() {
    setInterval(() => {
        const clockEl = document.getElementById('clock');
        if (clockEl) {
            clockEl.textContent = new Date().toLocaleTimeString();
        }
    }, 1000);
}

async function checkAuthentication() {
    try {
        const res = await fetch(`${BASE_URL}/auth/me`);
        if (res.ok) {
            const data = await res.json();
            loginSuccess(data);
        } else {
            showLoginScreen();
        }
    } catch (e) {
        showLoginScreen();
    }
}

function showLoginScreen() {
    document.getElementById('global-loader').classList.remove('active');
    document.getElementById('login-container').classList.add('active');
    document.getElementById('reset-password-container').classList.remove('active');
    document.getElementById('reset-password-container').classList.add('hide');
    document.getElementById('app-container').classList.add('hide');
    stopPolling();
}

async function loginSuccess(adminUser) {
    state.user = adminUser;

    // UI elements update
    document.getElementById('global-loader').classList.remove('active');
    document.getElementById('login-container').classList.remove('active');
    document.getElementById('app-container').classList.remove('hide');
    document.getElementById('admin-username').textContent = adminUser.username;

    // Initials avatar
    const avatarEl = document.getElementById('admin-avatar-initials');
    if (avatarEl) {
        avatarEl.textContent = adminUser.username.substring(0, 2).toUpperCase();
        avatarEl.style.fontWeight = 'bold';
    }

    const roleBadge = document.getElementById('admin-role-badge');
    const locationLbl = document.getElementById('admin-location-lbl');

    // Populate dynamic location selectors
    await populateDynamicBranchesAndLocations();

    // Hide or show reference tabs based on role
    const kbMenu = document.querySelector('.menu-item[data-tab="knowledge"]');
    const packagesMenu = document.querySelector('.menu-item[data-tab="packages"]');
    const feesMenu = document.querySelector('.menu-item[data-tab="fees"]');
    const branchesMenu = document.querySelector('.menu-item[data-tab="branches"]');
    const resourcesMenu = document.getElementById('menu-resources');

    if (adminUser.role === 'super_admin') {
        roleBadge.textContent = 'Super Admin';
        roleBadge.className = 'badge bg-blue';
        locationLbl.textContent = 'All Branches';
        document.getElementById('location-filter-wrapper').classList.remove('hide');
        document.getElementById('menu-admins').classList.remove('hide');

        if (kbMenu) kbMenu.classList.remove('hide');
        if (packagesMenu) packagesMenu.classList.remove('hide');
        if (feesMenu) feesMenu.classList.remove('hide');
        if (branchesMenu) branchesMenu.classList.remove('hide');
        if (resourcesMenu) resourcesMenu.classList.add('hide');
    } else {
        roleBadge.textContent = 'Branch Admin';
        roleBadge.className = 'badge bg-blue';
        locationLbl.textContent = `${adminUser.location} Branch`;

        // Hide Admin Management and lock/hide branch dropdown
        document.getElementById('location-filter-wrapper').classList.add('hide');
        document.getElementById('menu-admins').classList.add('hide');

        if (kbMenu) kbMenu.classList.add('hide');
        if (packagesMenu) packagesMenu.classList.add('hide');
        if (feesMenu) feesMenu.classList.add('hide');
        if (branchesMenu) branchesMenu.classList.add('hide');
        if (resourcesMenu) resourcesMenu.classList.remove('hide');

        // Lock select option to admin's location
        const locSelect = document.getElementById('location-select');
        if (locSelect) locSelect.value = adminUser.location;

        // Set default location filters for branch admin (can see other branches, defaults to own)
        const clientLocSelect = document.getElementById('filter-client-location');
        if (clientLocSelect) clientLocSelect.value = adminUser.location;

        const bookingLocSelect = document.getElementById('filter-booking-location');
        if (bookingLocSelect) bookingLocSelect.value = adminUser.location;

        // Support tickets location locked to branch admin's location
        const ticketLocSelect = document.getElementById('filter-ticket-location');
        if (ticketLocSelect) {
            ticketLocSelect.value = adminUser.location;
            ticketLocSelect.disabled = true;
        }
    }

    // Apply initial role restrictions in UI
    applyRoleRestrictions();

    // Load default tab
    navigateTo(state.currentPage);

    // Background polling for live chats
    setInterval(() => {
        pollIncomingChats();
    }, 4500);
}

async function populateDynamicBranchesAndLocations() {
    try {
        const res = await fetch(`${BASE_URL}/clients`);
        const branches = await res.json();
        state.locations = branches;

        const selects = [
            'location-select',
            'filter-client-location',
            'filter-booking-location',
            'filter-ticket-location',
            'ticket-edit-location'
        ];

        selects.forEach(id => {
            const selectEl = document.getElementById(id);
            if (selectEl) {
                selectEl.innerHTML = `<option value="">All Branches</option>`;
                branches.forEach(b => {
                    selectEl.innerHTML += `<option value="${escapeHTML(b.name)}">${escapeHTML(b.name)}</option>`;
                });
            }
        });

        const adminLocSelect = document.getElementById('admin-user-location');
        if (adminLocSelect) {
            adminLocSelect.innerHTML = '<option value="">None (Super Admin - All Locations)</option>';
            branches.forEach(b => {
                adminLocSelect.innerHTML += `<option value="${escapeHTML(b.name)}">${escapeHTML(b.name)}</option>`;
            });
        }
    } catch (e) {
        console.error('Failed to populate branches/locations', e);
    }
}

function applyRoleRestrictions() {
    const isBranchAdmin = state.user && state.user.role === 'branch_admin';

    // Disable components only Super Admins can manage
    document.querySelectorAll('.super-only').forEach(el => {
        if (isBranchAdmin) {
            el.classList.add('hide');
        } else {
            el.classList.remove('hide');
        }
    });

    // Disable adding branches or fees for branch admin
    const addBranchBtn = document.getElementById('btn-add-branch');
    const addFeeBtn = document.getElementById('btn-add-fee');
    if (isBranchAdmin) {
        if (addBranchBtn) addBranchBtn.classList.add('hide');
        if (addFeeBtn) addFeeBtn.classList.add('hide');
    } else {
        if (addBranchBtn) addBranchBtn.classList.remove('hide');
        if (addFeeBtn) addFeeBtn.classList.remove('hide');
    }
}

// ==========================================
// SPA Router & Navigation
// ==========================================
function navigateTo(tabId) {
    const isBranchAdmin = state.user && state.user.role === 'branch_admin';
    const restrictedTabs = ['knowledge', 'packages', 'fees', 'branches'];
    if (isBranchAdmin && restrictedTabs.includes(tabId)) {
        navigateTo('resources');
        return;
    }

    state.currentPage = tabId;

    // Update Menu selection
    document.querySelectorAll('.menu-item').forEach(item => {
        if (item.getAttribute('data-tab') === tabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update Panel view
    document.querySelectorAll('.tab-panel').forEach(panel => {
        if (panel.getAttribute('id') === `panel-${tabId}`) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });

    // Update Header title
    const pageTitles = {
        'overview': 'Operational Overview',
        'chats': 'Live Chat Workspace',
        'broadcast': 'Broadcasts',
        'knowledge': 'Knowledge Base Management',
        'packages': 'Packages',
        'fees': 'Add-On Checkout Fees',
        'branches': 'Office Branches',
        'resources': 'School Info & References',
        'clients': 'Registered Clients Directory',
        'registrations': 'Package Registrations',
        'tickets': 'Support Tickets Helpdesk',
        'chat-analysis': 'AI Semantic Analytics',
        'admins': 'Manage Administrator Users'
    };
    document.getElementById('page-title').textContent = pageTitles[tabId] || tabId;

    // Stop chat polling if leaving chat panel
    if (tabId !== 'chats') {
        stopChatPolling();
    }

    // Load page-specific data
    loadPageData(tabId);
}

function loadPageData(tabId) {
    const loc = getSelectedLocation();
    showPageLoading();
    switch (tabId) {
        case 'overview':
            loadMetrics(loc);
            loadRecentRegistrations(loc);
            loadOverviewChart();
            loadMessageAnalytics();
            loadRegistrationAnalytics();
            break;
        case 'chats':
            loadChatThreads(loc);
            break;
        case 'broadcast':
            loadBroadcastHistory();
            populateBroadcastTargets();
            break;
        case 'knowledge':
            loadKnowledgeBase();
            loadKnowledgeStats();
            loadDocumentsList();
            break;
        case 'packages':
            loadPackages();
            break;
        case 'fees':
            loadAddonFees();
            break;
        case 'branches':
            loadBranches();
            break;
        case 'resources':
            loadResourcesPage();
            break;
        case 'clients':
            loadRegisteredClients();
            break;
        case 'registrations':
            loadBookings();
            loadPackagesForFilters();
            loadRegistrationAnalyticsPage();
            break;
        case 'tickets':
            loadTickets(loc);
            loadTicketAnalyticsPage();
            break;
        case 'chat-analysis':
            loadChatAnalysisTab();
            break;
        case 'admins':
            loadAdmins();
            break;
    }
    setTimeout(hidePageLoading, 600);
}

function getSelectedLocation() {
    if (state.user && state.user.role === 'branch_admin') {
        return state.user.location;
    }
    const selectEl = document.getElementById('location-select');
    return selectEl ? selectEl.value : '';
}

// ==========================================
// Data Fetchers & Renders
// ==========================================

// --- Overview Metric Panels ---
async function loadMetrics(loc) {
    try {
        const query = loc ? `?location=${loc}` : '';
        const res = await fetch(`${BASE_URL}/metrics${query}`);
        const data = await res.json();

        const branchUsers = data.total_users || 0;
        const globalUsers = data.global_total_users || 0;

        document.getElementById('metric-users').textContent = branchUsers;

        const splitEl = document.getElementById('metric-users-split');
        if (splitEl) {
            const locName = getSelectedLocation() || (state.user && state.user.role === 'branch_admin' ? state.user.location : '');
            if (locName) {
                splitEl.textContent = `${locName}: ${branchUsers} | Whole Bot: ${globalUsers}`;
            } else {
                splitEl.textContent = `Whole Bot: ${globalUsers}`;
            }
        }

        document.getElementById('metric-registrations').textContent = data.total_registrations || 0;
        document.getElementById('metric-revenue').textContent = `GHS ${(data.total_revenue || 0).toFixed(2)}`;
        document.getElementById('metric-tickets').textContent = data.open_tickets || 0;
    } catch (e) {
        console.error('Failed to load metrics', e);
    }
}

async function loadRecentRegistrations(loc) {
    try {
        const query = loc ? `?location=${loc}` : '';
        const res = await fetch(`${BASE_URL}/registrations${query}`);
        const registrations = await res.json();

        const tbody = document.getElementById('tbl-recent-registrations');
        tbody.innerHTML = '';

        if (registrations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No recent signups.</td></tr>';
            return;
        }

        // Show first 5
        registrations.slice(0, 5).forEach(r => {
            const statusClass = r.status === 'confirmed' ? 'badge-success' : (r.status === 'pending' ? 'badge-warning' : 'badge-danger');
            tbody.innerHTML += `
                <tr>
                    <td>
                        <strong>${escapeHTML(r.user_name || 'Guest')}</strong><br>
                        <small>${escapeHTML(r.phone_number)}</small>
                    </td>
                    <td>${escapeHTML(r.package_name)}</td>
                    <td>${escapeHTML(r.user_location || 'Unknown')}</td>
                    <td><span class="badge ${statusClass}">${escapeHTML(r.status)}</span></td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load recent registrations', e);
    }
}

async function loadOverviewChart() {
    try {
        const response = await fetch(`${BASE_URL}/overview/trends?days=7`);
        if (!response.ok) return;
        const trend = await response.json();

        const labels = trend.messages.map(item => item.day);
        const messagesCount = trend.messages.map(item => item.count);
        const registrationsCount = trend.registrations.map(item => item.count);

        if (state.overviewChart) {
            state.overviewChart.destroy();
        }

        const ctx = document.getElementById('overview-chart').getContext('2d');
        state.overviewChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'WhatsApp Messages',
                        data: messagesCount,
                        borderColor: '#c62828',
                        backgroundColor: 'rgba(198, 40, 40, 0.05)',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Registrations',
                        data: registrationsCount,
                        borderColor: '#1a237e',
                        backgroundColor: 'rgba(26, 35, 126, 0.05)',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#1a1a2e', font: { family: 'Inter' } } }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280' } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280', precision: 0 } }
                }
            }
        });
    } catch (e) {
        console.error('Error rendering overview trend charts:', e);
    }
}

async function loadMessageAnalytics(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById('btn-msg-filter');
    if (btn && e) setButtonLoading(btn, true);

    try {
        const start = document.getElementById('msg-filter-start').value;
        const end = document.getElementById('msg-filter-end').value;
        const dir = document.getElementById('msg-filter-dir').value;

        if (!start || !end) return;

        const response = await fetch(`${BASE_URL}/overview/message-analytics?start_date=${start}&end_date=${end}&direction=${dir}`);
        if (!response.ok) throw new Error('Failed to fetch analytics');
        const data = await response.json();

        document.getElementById('msg-filter-total').innerText = data.totals.total_messages;
        document.getElementById('msg-filter-users').innerText = data.totals.unique_users;

        const labels = data.trend.map(item => item.day);
        const counts = data.trend.map(item => item.count);

        if (state.msgAnalyticsChart) {
            state.msgAnalyticsChart.destroy();
        }

        const ctx = document.getElementById('msg-analytics-chart').getContext('2d');
        state.msgAnalyticsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: `Messages (${dir === 'both' ? 'Sent & Received' : dir.charAt(0).toUpperCase() + dir.slice(1)})`,
                        data: counts,
                        borderColor: '#2e7d32',
                        backgroundColor: 'rgba(46, 125, 50, 0.05)',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#1a1a2e', font: { family: 'Inter' } } }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280' } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280', precision: 0 } }
                }
            }
        });
    } catch (e) {
        console.error('Error loading message analytics', e);
    } finally {
        if (btn && e) setButtonLoading(btn, false, '<i class="fa-solid fa-filter"></i> Apply Filter');
        setTimeout(hidePageLoading, 500);
    }
}

async function loadRegistrationAnalytics(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById('btn-reg-filter');
    if (btn && e) setButtonLoading(btn, true);

    try {
        const start = document.getElementById('reg-filter-start').value;
        const end = document.getElementById('reg-filter-end').value;
        const status = document.getElementById('reg-filter-status').value;

        if (!start || !end) return;

        const response = await fetch(`${BASE_URL}/overview/registration-analytics?start_date=${start}&end_date=${end}&status=${status}`);
        if (!response.ok) throw new Error('Failed to fetch registration analytics');
        const data = await response.json();

        document.getElementById('reg-filter-total').innerText = data.totals.total_registrations;
        document.getElementById('reg-filter-pending').innerText = data.totals.pending_registrations;

        const labels = data.trend.map(item => item.day);
        const counts = data.trend.map(item => item.count);

        if (state.regAnalyticsChart) {
            state.regAnalyticsChart.destroy();
        }

        const ctx = document.getElementById('reg-analytics-chart').getContext('2d');
        state.regAnalyticsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: `Registrations (${status.charAt(0).toUpperCase() + status.slice(1)})`,
                        data: counts,
                        borderColor: '#1565c0',
                        backgroundColor: 'rgba(21, 101, 192, 0.05)',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#1a1a2e', font: { family: 'Inter' } } }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280' } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280', precision: 0 } }
                }
            }
        });
    } catch (e) {
        console.error('Error loading registration analytics', e);
    } finally {
        if (btn && e) setButtonLoading(btn, false, '<i class="fa-solid fa-filter"></i> Apply Filter');
        setTimeout(hidePageLoading, 500);
    }
}

async function loadRegistrationAnalyticsPage(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById('btn-reg-filter-page');
    if (btn && e) setButtonLoading(btn, true);

    try {
        const start = document.getElementById('reg-filter-start-page').value;
        const end = document.getElementById('reg-filter-end-page').value;
        const status = document.getElementById('reg-filter-status-page').value;

        if (!start || !end) return;

        const response = await fetch(`${BASE_URL}/overview/registration-analytics?start_date=${start}&end_date=${end}&status=${status}`);
        if (!response.ok) throw new Error('Failed to fetch registration analytics');
        const data = await response.json();

        document.getElementById('reg-filter-total-page').innerText = data.totals.total_registrations;
        document.getElementById('reg-filter-pending-page').innerText = data.totals.pending_registrations;

        const labels = data.trend.map(item => item.day);
        const counts = data.trend.map(item => item.count);

        if (state.regAnalyticsChartPage) {
            state.regAnalyticsChartPage.destroy();
        }

        const ctx = document.getElementById('reg-analytics-chart-page').getContext('2d');
        state.regAnalyticsChartPage = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `Registrations (${status.charAt(0).toUpperCase() + status.slice(1)})`,
                    data: counts,
                    borderColor: '#1565c0',
                    backgroundColor: 'rgba(21, 101, 192, 0.05)',
                    tension: 0.3, fill: true
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#1a1a2e', font: { family: 'Inter' } } } },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280' } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280', precision: 0 } }
                }
            }
        });
    } catch (e) {
        console.error('Error loading registration analytics page', e);
    } finally {
        if (btn && e) setButtonLoading(btn, false, '<i class="fa-solid fa-filter"></i> Apply Filter');
        setTimeout(hidePageLoading, 500);
    }
}

async function loadTicketAnalyticsPage(e) {
    if (e) e.preventDefault();
    const btn = document.getElementById('btn-ticket-filter-page');
    if (btn && e) setButtonLoading(btn, true);

    try {
        const start = document.getElementById('ticket-filter-start-page').value;
        const end = document.getElementById('ticket-filter-end-page').value;
        const status = document.getElementById('ticket-filter-status-page').value;

        if (!start || !end) return;

        const response = await fetch(`${BASE_URL}/overview/ticket-analytics?start_date=${start}&end_date=${end}&status=${status}`);
        if (!response.ok) throw new Error('Failed to fetch ticket analytics');
        const data = await response.json();

        document.getElementById('ticket-filter-total-page').innerText = data.totals.total_tickets;
        document.getElementById('ticket-filter-open-page').innerText = data.totals.open_tickets;

        const labels = data.trend.map(item => item.day);
        const counts = data.trend.map(item => item.count);

        if (state.ticketAnalyticsChartPage) {
            state.ticketAnalyticsChartPage.destroy();
        }

        const ctx = document.getElementById('ticket-analytics-chart-page').getContext('2d');
        state.ticketAnalyticsChartPage = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `Tickets (${status.charAt(0).toUpperCase() + status.slice(1)})`,
                    data: counts,
                    borderColor: '#ff8f00',
                    backgroundColor: 'rgba(255, 143, 0, 0.05)',
                    tension: 0.3, fill: true
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#1a1a2e', font: { family: 'Inter' } } } },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280' } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: '#6b7280', precision: 0 } }
                }
            }
        });
    } catch (e) {
        console.error('Error loading ticket analytics page', e);
    } finally {
        if (btn && e) setButtonLoading(btn, false, '<i class="fa-solid fa-filter"></i> Apply Filter');
        setTimeout(hidePageLoading, 500);
    }
}

// --- Live Chats & Human Toggle ---
async function loadChatThreads(loc) {
    try {
        const query = loc ? `?location=${loc}` : '';
        const res = await fetch(`${BASE_URL}/chats${query}`);
        const chats = await res.json();

        const container = document.getElementById('chat-threads');
        container.innerHTML = '';

        if (chats.length === 0) {
            container.innerHTML = '<p class="placeholder-text">No active chats found.</p>';
            return;
        }

        chats.forEach(c => {
            const isActive = state.activeChatPhone === c.phone_number ? 'active' : '';
            const msgTime = c.last_message_time ? formatRelativeTime(c.last_message_time) : '';
            const lastMsg = c.last_message || 'No messages yet';
            const townText = c.town ? ` (${c.town})` : '';
            const locationText = c.location ? ` | ${c.location}` : '';

            container.innerHTML += `
                <div class="chat-thread ${isActive}" onclick="selectChat('${c.phone_number}')">
                    <div class="avatar"><i class="fa-solid fa-user"></i></div>
                    <div class="thread-details">
                        <div class="thread-header">
                            <h4>${escapeHTML(c.name || 'Guest')}</h4>
                            <span>${msgTime}</span>
                        </div>
                        <div class="thread-body">
                            <p>${escapeHTML(lastMsg)}</p>
                            <small class="text-muted">${escapeHTML(c.phone_number)}${escapeHTML(townText)}${escapeHTML(locationText)}</small>
                            <div style="margin-top: 4px;">
                                ${c.is_human_chat === 1 ? '<span class="badge badge-danger" style="text-transform:none; font-size:9px;">Human Agent</span>' : '<span class="badge badge-success" style="text-transform:none; font-size:9px;">AI Bot</span>'}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load chat threads', e);
    }
}

async function selectChat(phone) {
    state.activeChatPhone = phone;
    document.querySelectorAll('.chat-thread').forEach(thread => {
        if (thread.innerHTML.includes(phone)) {
            thread.classList.add('active');
        } else {
            thread.classList.remove('active');
        }
    });

    document.getElementById('chat-window-empty').classList.add('hide');
    document.getElementById('chat-window-active').classList.remove('hide');

    // Reset delta polling state
    state.lastMessageTime = null;

    // Fetch info & messages
    await loadActiveChatHistory();

    // Start interval polling for chat history
    startChatPolling();
}

async function loadActiveChatHistory() {
    if (!state.activeChatPhone) return;
    try {
        const isPolling = !!state.lastMessageTime;
        let url = `${BASE_URL}/chats/${state.activeChatPhone}/messages?limit=50`;
        if (isPolling) {
            url += `&since=${encodeURIComponent(state.lastMessageTime)}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        // 1. Update headers ONLY if changed
        const nameEl = document.getElementById('active-chat-name');
        const newName = data.user.name || 'Guest';
        if (nameEl && nameEl.textContent !== newName) {
            nameEl.textContent = newName;
        }

        const locDetails = [data.user.town, data.user.location].filter(Boolean).join(' | ') || 'Unknown';
        const phoneEl = document.getElementById('active-chat-phone');
        const newPhoneText = `${data.user.phone_number} (${locDetails})`;
        if (phoneEl && phoneEl.textContent !== newPhoneText) {
            phoneEl.textContent = newPhoneText;
        }

        // 2. Update human mode toggle ONLY if changed
        const toggleBtn = document.getElementById('btn-toggle-human');
        const toggleText = document.getElementById('toggle-human-text');
        if (toggleBtn && toggleText) {
            const isHuman = !!data.user.is_human_chat;
            const currentIsHuman = toggleBtn.classList.contains('btn-danger');
            if (isHuman !== currentIsHuman) {
                if (isHuman) {
                    toggleBtn.className = 'btn btn-danger btn-sm';
                    toggleText.textContent = 'Human Agent Active';
                } else {
                    toggleBtn.className = 'btn btn-secondary btn-sm';
                    toggleText.textContent = 'AI Agent Active';
                }
            }
        }

        // 3. Message stream render - ONLY if messages changed
        const stream = document.getElementById('message-stream');
        if (stream) {
            if (data.messages.length > 0) {
                // Update lastMessageTime to the newest message
                const newestMsg = data.messages[data.messages.length - 1];
                if (newestMsg.created_at) {
                    state.lastMessageTime = newestMsg.created_at;
                }

                const shouldScroll = stream.scrollTop + stream.clientHeight >= stream.scrollHeight - 50;

                let html = '';
                data.messages.forEach(m => {
                    const bubbleClass = m.role === 'user' ? 'user' : (m.role === 'admin' ? 'admin' : 'assistant');
                    const senderTag = m.role === 'admin' ? '[Admin] ' : (m.role === 'assistant' ? '[Bot] ' : '');
                    const timeStr = m.created_at ? new Date(m.created_at.replace(' ', 'T')).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

                    html += `
                        <div class="message-bubble ${bubbleClass}">
                            <div>${senderTag}${escapeHTML(m.content)}</div>
                            <span class="message-meta">${timeStr}</span>
                        </div>
                    `;
                });

                if (isPolling) {
                    // Remove "No messages" placeholder if it exists
                    if (stream.innerHTML.includes('No messages recorded')) {
                        stream.innerHTML = '';
                    }
                    stream.insertAdjacentHTML('beforeend', html);
                } else {
                    stream.innerHTML = html;
                }

                if (shouldScroll) {
                    stream.scrollTop = stream.scrollHeight;
                }
            } else if (!isPolling) {
                // Initial load with 0 messages
                stream.innerHTML = '<div class="message-bubble system">No messages recorded.</div>';
            }
        }
    } catch (e) {
        console.error('Failed to load active chat history', e);
    }
}

function startChatPolling() {
    stopChatPolling();
    state.chatPollInterval = setInterval(loadActiveChatHistory, 3000);
}

function stopChatPolling() {
    if (state.chatPollInterval) {
        clearInterval(state.chatPollInterval);
        state.chatPollInterval = null;
    }
}

function stopPolling() {
    stopChatPolling();
}

async function pollIncomingChats() {
    if (!state.user) return;
    try {
        const loc = getSelectedLocation();
        const query = loc ? `?location=${loc}` : '';
        const response = await fetch(`${BASE_URL}/chats${query}`);
        if (!response.ok) return;
        const chats = await response.json();

        const newChatsStr = JSON.stringify(chats);
        const oldChatsStr = JSON.stringify(state.chatsList || []);
        
        if (newChatsStr !== oldChatsStr) {
            state.chatsList = chats;
            renderChatsSidebarOnly(chats);
        }

    } catch (e) {
        console.error('Error polling chats:', e);
    }
}

function renderChatsSidebarOnly(chats) {
    const container = document.getElementById('chat-threads');
    if (!container) return;

    let html = '';
    const searchVal = document.getElementById('chat-search').value.toLowerCase();

    chats.forEach(c => {
        const matchesName = c.name && c.name.toLowerCase().includes(searchVal);
        const matchesPhone = c.phone_number && c.phone_number.includes(searchVal);
        if (searchVal && !matchesName && !matchesPhone) return;

        const isActive = state.activeChatPhone === c.phone_number ? 'active' : '';
        const msgTime = c.last_message_time ? formatRelativeTime(c.last_message_time) : '';
        const lastMsg = c.last_message || 'No messages yet';
        const locationText = c.location ? ` | ${c.location}` : '';

        html += `
            <div class="chat-thread ${isActive}" onclick="selectChat('${c.phone_number}')">
                <div class="avatar"><i class="fa-solid fa-user"></i></div>
                <div class="thread-details">
                    <div class="thread-header">
                        <h4>${escapeHTML(c.name || 'Guest')}</h4>
                        <span>${msgTime}</span>
                    </div>
                    <div class="thread-body">
                        <p>${escapeHTML(lastMsg)}</p>
                        <small class="text-muted">${escapeHTML(c.phone_number)}${escapeHTML(locationText)}</small>
                        <div style="margin-top: 4px;">
                            ${c.is_human_chat === 1 ? '<span class="badge badge-danger" style="text-transform:none; font-size:9px;">Human Agent</span>' : '<span class="badge badge-success" style="text-transform:none; font-size:9px;">AI Bot</span>'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html || '<p class="placeholder-text">No active chats found.</p>';
}

function renderMessagesFeedOnly(messages) {
    const stream = document.getElementById('message-stream');
    if (!stream) return;
    stream.innerHTML = '';
    messages.forEach(m => {
        const bubbleClass = m.role === 'user' ? 'user' : (m.role === 'admin' ? 'admin' : 'assistant');
        const senderTag = m.role === 'admin' ? '[Admin] ' : (m.role === 'assistant' ? '[Bot] ' : '');
        const timeStr = m.created_at ? new Date(m.created_at.replace(' ', 'T')).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

        stream.innerHTML += `
            <div class="message-bubble ${bubbleClass}">
                <div>${senderTag}${escapeHTML(m.content)}</div>
                <span class="message-meta">${timeStr}</span>
            </div>
        `;
    });
    stream.scrollTop = stream.scrollHeight;
}

// --- Broadcast ---
async function populateBroadcastTargets() {
    // Cache branches and packages for the cascading dropdowns.
    try {
        const [branchRes, pkgRes] = await Promise.all([
            fetch(`${BASE_URL}/clients`),
            fetch(`${BASE_URL}/packages`),
        ]);
        const branchesData = await branchRes.json();
        const packagesData = await pkgRes.json();
        state.broadcastBranches = Array.isArray(branchesData) ? branchesData : [];
        state.broadcastPackages = Array.isArray(packagesData) ? packagesData : [];
    } catch (e) {
        console.error('Failed to populate broadcast targets', e);
        state.broadcastBranches = [];
        state.broadcastPackages = [];
    }

    // Wire the cascading dropdowns.
    const targetSelect = document.getElementById('broadcast-target');
    const branchGroup = document.getElementById('broadcast-branch-group');
    const branchList = document.getElementById('broadcast-branches-list');
    const packageGroup = document.getElementById('broadcast-package-group');
    const packageList = document.getElementById('broadcast-packages-list');

    const isBranchAdmin = state.user && state.user.role === 'branch_admin';

    // Populate dropdown based on role
    if (isBranchAdmin) {
        targetSelect.innerHTML = `
            <option value="branch">All Users in ${escapeHTML(state.user.location)}</option>
            <option value="package_branch">Users by Package in ${escapeHTML(state.user.location)}</option>
        `;
    } else {
        targetSelect.innerHTML = `
            <option value="all">All Users</option>
            <option value="branch">Users by Branch Location</option>
            <option value="package">Users by Package</option>
            <option value="package_branch">Users by Package at a Branch</option>
        `;
    }

    const updateSubFilters = () => {
        const kind = targetSelect.value;

        branchList.innerHTML = '';
        packageList.innerHTML = '';

        if ((kind === 'branch' || kind === 'package_branch') && !isBranchAdmin) {
            (state.broadcastBranches || []).forEach(b => {
                const label = document.createElement('label');
                label.className = 'checkbox-card';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'checkbox-input';
                checkbox.value = b.name;

                const content = document.createElement('div');
                content.className = 'card-content';

                const icon = document.createElement('div');
                icon.className = 'card-icon';
                icon.innerHTML = '<i class="fa-solid fa-building"></i>';

                const info = document.createElement('div');
                info.className = 'card-info';

                const title = document.createElement('span');
                title.className = 'card-title';
                title.textContent = b.name;

                const subtitle = document.createElement('span');
                subtitle.className = 'card-subtitle';
                subtitle.textContent = b.region || 'Unknown';

                info.appendChild(title);
                info.appendChild(subtitle);
                content.appendChild(icon);
                content.appendChild(info);

                label.appendChild(checkbox);
                label.appendChild(content);
                branchList.appendChild(label);
            });
            branchGroup.classList.remove('hide');
        } else {
            branchGroup.classList.add('hide');
        }

        if (kind === 'package' || kind === 'package_branch') {
            (state.broadcastPackages || []).forEach(p => {
                const label = document.createElement('label');
                label.className = 'checkbox-card';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'checkbox-input';
                checkbox.value = p.id;

                const content = document.createElement('div');
                content.className = 'card-content';

                const icon = document.createElement('div');
                icon.className = 'card-icon';
                icon.innerHTML = '<i class="fa-solid fa-car"></i>';

                const info = document.createElement('div');
                info.className = 'card-info';

                const title = document.createElement('span');
                title.className = 'card-title';
                title.textContent = p.name;

                const subtitle = document.createElement('span');
                subtitle.className = 'card-subtitle';
                subtitle.textContent = `${p.price} GHS • ${p.schedule_type} (${p.duration_weeks} wks)`;

                info.appendChild(title);
                info.appendChild(subtitle);
                content.appendChild(icon);
                content.appendChild(info);

                label.appendChild(checkbox);
                label.appendChild(content);
                packageList.appendChild(label);
            });
            packageGroup.classList.remove('hide');
        } else {
            packageGroup.classList.add('hide');
        }
    };

    targetSelect.removeEventListener('change', updateSubFilters);
    targetSelect.addEventListener('change', updateSubFilters);
    updateSubFilters();  // run once for the current value
}

async function loadBroadcastHistory() {
    try {
        const res = await fetch(`${BASE_URL}/broadcast`);
        const broadcasts = await res.json();

        const tbody = document.getElementById('tbl-broadcasts');
        tbody.innerHTML = '';

        if (broadcasts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No broadcasts dispatched.</td></tr>';
            return;
        }

        broadcasts.forEach(b => {
            const date = b.created_at ? new Date(b.created_at.replace(' ', 'T')).toLocaleDateString() : '-';
            tbody.innerHTML += `
                <tr>
                    <td>${date}</td>
                    <td>${escapeHTML(b.message.substring(0, 80))}...</td>
                    <td>${escapeHTML(b.sent_by_name || 'System')}</td>
                    <td><span class="badge bg-blue" style="color:var(--primary)!important;">${b.recipient_count} recipients</span></td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load broadcast history', e);
    }
}

// --- Knowledge Base ---
async function loadKnowledgeBase() {
    try {
        const res = await fetch(`${BASE_URL}/knowledge`);
        const kb = await res.json();

        const tbody = document.getElementById('tbl-knowledge');
        tbody.innerHTML = '';

        if (kb.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No structured Q&A records available.</td></tr>';
            return;
        }

        kb.forEach(k => {
            const isBranchAdmin = state.user && state.user.role === 'branch_admin';
            tbody.innerHTML += `
                <tr>
                    <td><strong>${escapeHTML(k.topic)}</strong></td>
                    <td>${escapeHTML(k.content.substring(0, 80))}...</td>
                    <td>${escapeHTML(k.source_file ? 'PDF Upload (' + k.source_file + ')' : 'Manual QA')}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="editKnowledge(${k.id})"><i class="fa-solid fa-edit"></i></button>
                        <button class="btn btn-danger btn-sm ${isBranchAdmin ? 'hide' : ''}" onclick="deleteKnowledge(${k.id})"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load knowledge base', e);
    }
}

async function loadKnowledgeStats() {
    try {
        const res = await fetch(`${BASE_URL}/documents/status`);
        if (res.ok) {
            const data = await res.json();
            const statDocs = document.getElementById('rag-stat-docs');
            const statChunks = document.getElementById('rag-stat-chunks');
            if (statDocs) statDocs.textContent = data.total_documents || 0;
            if (statChunks) statChunks.textContent = data.total_chunks || 0;
        }
    } catch (e) {
        console.error('Error fetching RAG status:', e);
    }
}

async function loadDocumentsList() {
    const tbody = document.getElementById('rag-documents-table');
    if (!tbody) return;
    try {
        const res = await fetch(`${BASE_URL}/documents`);
        if (!res.ok) return;
        const docs = await res.json();
        tbody.innerHTML = '';

        if (docs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="placeholder-text" style="font-size:12px; padding:10px;">No PDF manuals indexed yet.</td></tr>';
            return;
        }

        docs.forEach(doc => {
            tbody.innerHTML += `
                <tr>
                    <td style="font-size:12.5px;">
                        <i class="fa-solid fa-file-pdf" style="color:var(--primary); margin-right:6px;"></i>
                        <span>${escapeHTML(doc)}</span>
                    </td>
                    <td style="text-align:right;">
                        <button class="btn btn-danger btn-sm" onclick="deleteDocument('${escapeHTML(doc)}')">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Error loading documents list:', e);
    }
}

async function deleteDocument(filename) {
    if (!confirm(`Are you sure you want to delete ${filename} from ChromaDB vector store? This will erase all its chunks.`)) return;
    try {
        const res = await fetch(`${BASE_URL}/documents/${filename}`, { method: 'DELETE' });
        if (res.ok) {
            alert('Document chunks deleted successfully!');
            loadKnowledgeStats();
            loadDocumentsList();
            loadRAGStatus(); // sync status on RAG tab
        } else {
            const err = await res.json();
            alert(err.detail || 'Delete failed');
        }
    } catch (e) {
        alert('Network error');
    }
}
window.deleteDocument = deleteDocument;

// --- Packages ---
async function loadPackages() {
    try {
        const res = await fetch(`${BASE_URL}/packages`);
        const packages = await res.json();

        const container = document.getElementById('packages-cards-container');
        container.innerHTML = '';

        if (packages.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No lesson packages configured yet.</p>';
            return;
        }

        const categories = {};
        packages.forEach(p => {
            const cat = p.category || 'Non-Students';
            if (!categories[cat]) categories[cat] = [];
            categories[cat].push(p);
        });

        for (const [cat, items] of Object.entries(categories)) {
            container.innerHTML += `<div style="width: 100%; grid-column: 1 / -1;"><h4 style="margin-top: 10px; margin-bottom: 5px; border-bottom: 1px solid var(--border-color); padding-bottom: 5px;">${escapeHTML(cat)}</h4></div>`;
            items.forEach(p => {
                container.innerHTML += `
                    <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px;">
                        <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(p.name)}</h4>
                        </div>
                        <p style="font-size:12.5px; margin-bottom:10px; color:var(--text-muted);">${escapeHTML(p.description || 'No description provided.')}</p>
                        <div class="item-card-details" style="font-size:12px; display:flex; flex-direction:column; gap:6px;">
                            <div>
                                <i class="fa-solid fa-calendar-days" style="color:var(--primary); margin-right:4px;"></i>
                                <span>Schedule: <strong>${escapeHTML(p.schedule_type || 'Combined')}</strong></span>
                            </div>
                            <div>
                                <i class="fa-solid fa-hourglass-half" style="color:var(--primary); margin-right:4px;"></i>
                                <span>Duration: <strong>${escapeHTML(p.duration_weeks || '6')} Weeks</strong></span>
                            </div>
                            <div style="margin-top: 6px; font-size: 16px; font-weight: 800; color: var(--primary);">
                                GHS ${p.price.toFixed(2)}
                            </div>
                        </div>
                        <div class="item-card-actions" style="margin-top:14px; display:flex; gap:8px;">
                            <button class="btn btn-secondary btn-sm" onclick="editPackage(${p.id})"><i class="fa-solid fa-edit"></i> Edit</button>
                            <button class="btn btn-danger btn-sm" onclick="deletePackage(${p.id})"><i class="fa-solid fa-trash"></i></button>
                        </div>
                    </div>
                `;
            });
        }
    } catch (e) {
        console.error('Failed to load packages', e);
    }
}

// --- Add-On Fees ---
async function loadAddonFees() {
    try {
        const res = await fetch(`${BASE_URL}/fees`);
        const fees = await res.json();

        const container = document.getElementById('fees-cards-container');
        container.innerHTML = '';

        if (fees.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No checkout fees configured yet.</p>';
            return;
        }

        const isBranchAdmin = state.user && state.user.role === 'branch_admin';

        fees.forEach(f => {
            const mandatoryBadge = f.mandatory
                ? '<span class="badge bg-red" style="font-size: 9px; padding: 2px 6px;">Mandatory</span>'
                : '<span class="badge bg-blue" style="font-size: 9px; padding: 2px 6px; background:#e8f5e9 !important; color:#2e7d32 !important;">Optional</span>';
            const passThroughBadge = f.pass_through
                ? '<span class="badge" style="font-size: 9px; padding: 2px 6px; background:#fff3e0; color:#e65100; text-transform:none;">Pass-Through Cost</span>'
                : '<span class="badge" style="font-size: 9px; padding: 2px 6px; background:#eceff1; color:#37474f; text-transform:none;">Direct Fee</span>';

            container.innerHTML += `
                <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px;">
                    <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(f.name)}</h4>
                        ${mandatoryBadge}
                    </div>
                    <p style="font-size:12.5px; margin-bottom:10px; color:var(--text-muted);">${escapeHTML(f.description || 'No description.')}</p>
                    <div class="item-card-details" style="font-size:12px; display:flex; flex-direction:column; gap:6px;">
                        <div>
                            <i class="fa-solid fa-receipt" style="color:var(--primary); margin-right:4px;"></i>
                            <span>Type: ${passThroughBadge}</span>
                        </div>
                        <div style="margin-top: 6px; font-size: 16px; font-weight: 800; color: var(--primary);">
                            GHS ${f.amount.toFixed(2)}
                        </div>
                    </div>
                    <div class="item-card-actions" style="margin-top:14px; display:flex; gap:8px;">
                        <button class="btn btn-secondary btn-sm ${isBranchAdmin ? 'hide' : ''}" onclick="editFee(${f.id})"><i class="fa-solid fa-edit"></i> Edit</button>
                        <button class="btn btn-danger btn-sm ${isBranchAdmin ? 'hide' : ''}" onclick="deleteFee(${f.id})"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load add-on fees', e);
    }
}

// --- Branches ---
async function loadBranches() {
    try {
        const res = await fetch(`${BASE_URL}/clients`); // maps to Branch endpoint
        const branches = await res.json();

        const container = document.getElementById('branches-cards-container');
        container.innerHTML = '';

        if (branches.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No branches registered yet.</p>';
            return;
        }

        const isBranchAdmin = state.user && state.user.role === 'branch_admin';

        branches.forEach(b => {
            const mapsBtn = b.google_maps_link
                ? `<a href="${b.google_maps_link}" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-map-location-dot"></i> Maps</a>`
                : '';

            container.innerHTML += `
                <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px;">
                    <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(b.name)}</h4>
                        <span class="badge bg-blue" style="color:var(--primary)!important;">${escapeHTML(b.region || 'Unknown')}</span>
                    </div>
                    <div class="item-card-details" style="font-size:12.5px; display:flex; flex-direction:column; gap:6px; color:var(--text-muted); margin-bottom:10px;">
                        <div>
                            <i class="fa-solid fa-phone" style="color:var(--primary); margin-right:4px;"></i>
                            <span>${escapeHTML(b.contact_numbers || 'No phone')}</span>
                        </div>
                        <div>
                            <i class="fa-solid fa-location-dot" style="color:var(--primary); margin-right:4px;"></i>
                            <span>${escapeHTML(b.address || 'No address')}</span>
                        </div>
                    </div>
                    <div class="item-card-actions" style="display:flex; gap:8px;">
                        ${mapsBtn}
                        <button class="btn btn-secondary btn-sm ${isBranchAdmin ? 'hide' : ''}" onclick="editClient(${b.id})"><i class="fa-solid fa-edit"></i> Edit</button>
                        <button class="btn btn-danger btn-sm ${isBranchAdmin ? 'hide' : ''}" onclick="deleteClient(${b.id})"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load branches', e);
    }
}

// --- Consolidated Resources (View Only for Branch Admins) ---
async function loadResourcesPage() {
    // Clear search query
    const searchEl = document.getElementById('resources-search');
    if (searchEl) searchEl.value = '';

    await Promise.all([
        loadResourcesKnowledge(),
        loadResourcesBranches(),
        loadResourcesPackages(),
        loadResourcesFees()
    ]);
}

async function loadResourcesKnowledge() {
    try {
        const res = await fetch(`${BASE_URL}/knowledge`);
        const kb = await res.json();
        const tbody = document.getElementById('tbl-resources-knowledge');
        tbody.innerHTML = '';
        if (kb.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="placeholder-text">No structured Q&A records available.</td></tr>';
            return;
        }
        kb.forEach(k => {
            tbody.innerHTML += `
                <tr>
                    <td><strong>${escapeHTML(k.topic)}</strong></td>
                    <td>${escapeHTML(k.content)}</td>
                    <td><span class="badge" style="background:#e3f2fd; color:#0d47a1; text-transform:none;">${escapeHTML(k.source_file ? 'PDF Upload (' + k.source_file + ')' : 'Manual QA')}</span></td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load resources knowledge base', e);
    }
}

async function loadResourcesBranches() {
    try {
        const res = await fetch(`${BASE_URL}/clients`);
        const branches = await res.json();
        const container = document.getElementById('resources-branches-grid');
        container.innerHTML = '';
        if (branches.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No branches registered yet.</p>';
            return;
        }
        branches.forEach(b => {
            const mapsBtn = b.google_maps_link
                ? `<a href="${b.google_maps_link}" target="_blank" class="btn btn-secondary btn-sm" style="margin-top:auto;"><i class="fa-solid fa-map-location-dot"></i> Open in Maps</a>`
                : '';
            container.innerHTML += `
                <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px; display:flex; flex-direction:column; justify-content:space-between; height:100%;">
                    <div>
                        <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(b.name)}</h4>
                            <span class="badge bg-blue" style="color:var(--primary)!important;">${escapeHTML(b.region || 'Unknown')}</span>
                        </div>
                        <div class="item-card-details" style="font-size:12.5px; display:flex; flex-direction:column; gap:6px; color:var(--text-muted); margin-bottom:12px;">
                            <div>
                                <i class="fa-solid fa-phone" style="color:var(--primary); margin-right:4px;"></i>
                                <span>${escapeHTML(b.contact_numbers || 'No phone')}</span>
                            </div>
                            <div>
                                <i class="fa-solid fa-location-dot" style="color:var(--primary); margin-right:4px;"></i>
                                <span>${escapeHTML(b.address || 'No address')}</span>
                            </div>
                        </div>
                    </div>
                    ${mapsBtn}
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load resources branches', e);
    }
}

async function loadResourcesPackages() {
    try {
        const res = await fetch(`${BASE_URL}/packages`);
        const packages = await res.json();
        const container = document.getElementById('resources-packages-grid');
        container.innerHTML = '';
        if (packages.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No lesson packages configured yet.</p>';
            return;
        }
        packages.forEach(p => {
            container.innerHTML += `
                <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px; display:flex; flex-direction:column; justify-content:space-between; height:100%;">
                    <div>
                        <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(p.name)}</h4>
                        </div>
                        <p style="font-size:12.5px; margin-bottom:10px; color:var(--text-muted);">${escapeHTML(p.description || 'No description.')}</p>
                        <div class="item-card-details" style="font-size:12px; display:flex; flex-direction:column; gap:6px; margin-bottom:12px;">
                            <div>
                                <i class="fa-solid fa-calendar-days" style="color:var(--primary); margin-right:4px;"></i>
                                <span>Schedule: <strong>${escapeHTML(p.schedule_type || 'Combined')}</strong></span>
                            </div>
                            <div>
                                <i class="fa-solid fa-hourglass-half" style="color:var(--primary); margin-right:4px;"></i>
                                <span>Duration: <strong>${escapeHTML(p.duration_weeks || '6')} Weeks</strong></span>
                            </div>
                        </div>
                    </div>
                    <div style="font-size: 16px; font-weight: 800; color: var(--primary);">
                        GHS ${p.price.toFixed(2)}
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load resources packages', e);
    }
}

async function loadResourcesFees() {
    try {
        const res = await fetch(`${BASE_URL}/fees`);
        const fees = await res.json();
        const container = document.getElementById('resources-fees-grid');
        container.innerHTML = '';
        if (fees.length === 0) {
            container.innerHTML = '<p class="placeholder-text" style="width:100%;">No checkout fees configured yet.</p>';
            return;
        }
        fees.forEach(f => {
            const mandatoryBadge = f.mandatory
                ? '<span class="badge bg-red" style="font-size: 9px; padding: 2px 6px;">Mandatory</span>'
                : '<span class="badge bg-blue" style="font-size: 9px; padding: 2px 6px; background:#e8f5e9 !important; color:#2e7d32 !important;">Optional</span>';
            const passThroughBadge = f.pass_through
                ? '<span class="badge" style="font-size: 9px; padding: 2px 6px; background:#fff3e0; color:#e65100; text-transform:none;">Pass-Through Cost</span>'
                : '<span class="badge" style="font-size: 9px; padding: 2px 6px; background:#eceff1; color:#37474f; text-transform:none;">Direct Fee</span>';

            container.innerHTML += `
                <div class="item-card glass-card" style="border: 1px solid var(--border-color); padding: 18px; border-radius:10px; display:flex; flex-direction:column; justify-content:space-between; height:100%;">
                    <div>
                        <div class="item-card-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <h4 class="item-card-title" style="font-size:14px; font-weight:700;">${escapeHTML(f.name)}</h4>
                            ${mandatoryBadge}
                        </div>
                        <p style="font-size:12.5px; margin-bottom:10px; color:var(--text-muted);">${escapeHTML(f.description || 'No description.')}</p>
                        <div class="item-card-details" style="font-size:12px; display:flex; flex-direction:column; gap:6px; margin-bottom:12px;">
                            <div>
                                <i class="fa-solid fa-receipt" style="color:var(--primary); margin-right:4px;"></i>
                                <span>Type: ${passThroughBadge}</span>
                            </div>
                        </div>
                    </div>
                    <div style="font-size: 16px; font-weight: 800; color: var(--primary);">
                        GHS ${f.amount.toFixed(2)}
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error('Failed to load resources fees', e);
    }
}

function filterResourcesData() {
    const searchInput = document.getElementById('resources-search');
    if (!searchInput) return;
    const query = searchInput.value.toLowerCase().trim();

    // 1. Filter Knowledge base rows
    const kbRows = document.querySelectorAll('#tbl-resources-knowledge tr');
    kbRows.forEach(row => {
        if (row.querySelector('.placeholder-text')) return;
        const text = row.textContent.toLowerCase();
        if (text.includes(query)) {
            row.classList.remove('hide');
        } else {
            row.classList.add('hide');
        }
    });

    // 2. Filter Branches cards
    const branchCards = document.querySelectorAll('#resources-branches-grid .item-card');
    branchCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (text.includes(query)) {
            card.classList.remove('hide');
        } else {
            card.classList.add('hide');
        }
    });

    // 3. Filter Packages cards
    const packageCards = document.querySelectorAll('#resources-packages-grid .item-card');
    packageCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (text.includes(query)) {
            card.classList.remove('hide');
        } else {
            card.classList.add('hide');
        }
    });

    // 4. Filter Fees cards
    const feeCards = document.querySelectorAll('#resources-fees-grid .item-card');
    feeCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (text.includes(query)) {
            card.classList.remove('hide');
        } else {
            card.classList.add('hide');
        }
    });
}

// --- Registered Clients ---
async function loadRegisteredClients() {
    try {
        const loc = document.getElementById('filter-client-location').value;
        const search = document.getElementById('filter-client-search').value;
        const params = new URLSearchParams();
        if (loc) params.append('location', loc);
        if (search) params.append('search', search);

        const res = await fetch(`${BASE_URL}/clients-list?${params.toString()}`);
        const clients = await res.json();

        const tbody = document.getElementById('tbl-registered-clients');
        tbody.innerHTML = '';

        if (clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="placeholder-text">No registered clients found.</td></tr>';
            document.getElementById('btn-send-clients-msg').disabled = true;
            return;
        }

        clients.forEach(c => {
            const lastBooking = c.created_at ? new Date(c.created_at.replace(' ', 'T')).toLocaleDateString() : '-';
            tbody.innerHTML += `
                <tr>
                    <td><input type="checkbox" class="check-client" data-phone="${c.phone_number}" data-name="${escapeHTML(c.name || 'Guest')}"></td>
                    <td><strong>${escapeHTML(c.name || 'Guest')}</strong></td>
                    <td>${escapeHTML(c.phone_number)}</td>
                    <td>${escapeHTML(c.town || '-')}</td>
                    <td><span class="badge" style="background:#e0f2f1; color:#004d40; border:1px solid #b2dfdb; font-size:11px; padding:3px 8px;">${escapeHTML(c.location || 'All Branches')}</span></td>
                    <td>Intake Active</td>
                    <td>WhatsApp bot</td>
                    <td>${lastBooking}</td>
                </tr>
            `;
        });

        // Add event listeners
        document.querySelectorAll('.check-client').forEach(cb => {
            cb.addEventListener('change', updateClientCheckboxState);
        });
        updateClientCheckboxState();
    } catch (e) {
        console.error('Failed to load registered clients', e);
    }
}

function updateClientCheckboxState() {
    const checkboxes = document.querySelectorAll('.check-client');
    const btn = document.getElementById('btn-send-clients-msg');
    const selectAll = document.getElementById('check-all-clients');

    const checked = document.querySelectorAll('.check-client:checked');
    btn.disabled = checked.length === 0;
    btn.textContent = checked.length > 0 ? `Send Message (${checked.length})` : 'Send Message';
}

// --- Bookings / Registrations ---
async function loadBookings() {
    try {
        const loc = document.getElementById('filter-booking-location').value;
        const status = document.getElementById('filter-booking-status').value;
        const packageId = document.getElementById('filter-booking-package').value;
        const search = document.getElementById('filter-booking-search').value;
        const startDate = document.getElementById('filter-booking-start-date').value;
        const endDate = document.getElementById('filter-booking-end-date').value;
        const params = new URLSearchParams();
        if (loc) params.append('location', loc);
        if (status) params.append('status', status);
        if (packageId) params.append('package_id', packageId);
        if (search) params.append('search', search);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);

        const res = await fetch(`${BASE_URL}/registrations?${params.toString()}`);
        const bookings = await res.json();

        const tbody = document.getElementById('tbl-bookings');
        tbody.innerHTML = '';

        if (bookings.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="placeholder-text">No registrations found.</td></tr>';
            document.getElementById('btn-send-bookings-msg').disabled = true;
            return;
        }

        bookings.forEach(b => {
            const date = b.created_at ? new Date(b.created_at.replace(' ', 'T')).toLocaleDateString() : '-';
            const statusClass = b.status === 'confirmed' ? 'badge-success' : (b.status === 'pending' ? 'badge-warning' : 'badge-danger');
            tbody.innerHTML += `
                <tr>
                    <td><input type="checkbox" class="check-booking" data-id="${b.id}" data-phone="${b.phone_number}" data-name="${escapeHTML(b.user_name || 'Guest')}"></td>
                    <td><strong>${escapeHTML(b.user_name || 'Guest')}</strong></td>
                    <td>${escapeHTML(b.phone_number)}</td>
                    <td>${escapeHTML(b.package_name)}</td>
                    <td>GHS ${b.price ? b.price.toFixed(2) : '0.00'}</td>
                    <td><span class="badge ${statusClass}">${escapeHTML(b.status)}</span></td>
                    <td>${date}</td>
                    <td>${escapeHTML(b.user_location || '-')}</td>
                    <td>
                        ${b.status === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="checkPayment(${b.id})" title="Check Paystack Payment"><i class="fa-solid fa-credit-card"></i></button>` : ''}
                        <button class="btn btn-secondary btn-sm" onclick="editBooking(${b.id})" title="Edit Booking"><i class="fa-solid fa-edit"></i></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteBooking(${b.id})" title="Delete Booking"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });

        // Add event listeners
        document.querySelectorAll('.check-booking').forEach(cb => {
            cb.addEventListener('change', updateBookingCheckboxState);
        });
        updateBookingCheckboxState();
    } catch (e) {
        console.error('Failed to load bookings', e);
    }
}

function updateBookingCheckboxState() {
    const checkboxes = document.querySelectorAll('.check-booking');
    const btn = document.getElementById('btn-send-bookings-msg');

    const checked = document.querySelectorAll('.check-booking:checked');
    btn.disabled = checked.length === 0;
    btn.textContent = checked.length > 0 ? `Send Message (${checked.length})` : 'Send Message';
}

// --- Load packages for filter dropdowns ---
async function loadPackagesForFilters() {
    try {
        const res = await fetch(`${BASE_URL}/packages`);
        const packages = await res.json();

        const bookingSelect = document.getElementById('filter-booking-package');
        if (bookingSelect) {
            bookingSelect.innerHTML = '<option value="">All Packages</option>';
            packages.forEach(p => {
                bookingSelect.innerHTML += `<option value="${p.id}">${escapeHTML(p.name)}</option>`;
            });
        }

        const editBookingSelect = document.getElementById('booking-edit-package');
        if (editBookingSelect) {
            editBookingSelect.innerHTML = '';
            packages.forEach(p => {
                editBookingSelect.innerHTML += `<option value="${p.id}">${escapeHTML(p.name)}</option>`;
            });
        }
    } catch (e) {
        console.error('Failed to load packages for filters', e);
    }
}

// --- Open Send Message Modal ---
function openSendMessageModal(mode) {
    let ids = [];
    let label = '';

    if (mode === 'clients') {
        const checked = document.querySelectorAll('.check-client:checked');
        checked.forEach(cb => {
            ids.push({ phone: cb.dataset.phone, name: cb.dataset.name });
        });
        label = `Recipients: ${ids.length} client(s) selected`;
    } else if (mode === 'bookings') {
        const checked = document.querySelectorAll('.check-booking:checked');
        checked.forEach(cb => {
            ids.push({ id: parseInt(cb.dataset.id), phone: cb.dataset.phone, name: cb.dataset.name });
        });
        label = `Recipients: ${ids.length} booking(s) selected`;
    }

    if (ids.length === 0) return;

    document.getElementById('send-msg-ids').value = JSON.stringify(ids);
    document.getElementById('send-msg-mode').value = mode;
    document.getElementById('send-msg-recipients-label').textContent = label;
    document.getElementById('send-msg-text').value = '';
    openModal('modal-send-message');
}

// --- Support Tickets ---
async function loadTickets(loc) {
    try {
        const query = loc ? `?location=${loc}` : '';
        const res = await fetch(`${BASE_URL}/tickets${query}`);
        const tickets = await res.json();

        const tbody = document.getElementById('tbl-tickets');
        tbody.innerHTML = '';

        if (tickets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="placeholder-text">No support tickets recorded.</td></tr>';
            return;
        }

        tickets.forEach(t => {
            const statusClass = t.status === 'open' ? 'badge-danger' : (t.status === 'resolved' ? 'badge-success' : 'badge-warning');
            const date = t.created_at ? new Date(t.created_at.replace(' ', 'T')).toLocaleDateString() : '-';

            tbody.innerHTML += `
                <tr>
                    <td>
                        <strong>${escapeHTML(t.user_name || 'Guest')}</strong><br>
                        <small>${escapeHTML(t.phone_number)}</small>
                    </td>
                    <td><span class="badge" style="background:#e0f2f1; color:#004d40; border:1px solid #b2dfdb; font-size:11px; padding:3px 8px;">${escapeHTML(t.location || 'All Branches')}</span></td>
                    <td><strong>${escapeHTML(t.subject)}</strong></td>
                    <td>${escapeHTML(t.description || '-')}</td>
                    <td><span class="badge ${statusClass}">${escapeHTML(t.status)}</span></td>
                    <td>${date}</td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="chatWithTicketUser('${escapeHTML(t.phone_number)}')" title="Chat with this user">
                            <i class="fa-solid fa-comments"></i>
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="editTicket(${t.id})" title="Edit Ticket"><i class="fa-solid fa-edit"></i></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteTicket(${t.id})" title="Delete Ticket"><i class="fa-solid fa-trash"></i></button>
                        ${t.status === 'open' ? `<button class="btn btn-secondary btn-sm" onclick="resolveTicket(${t.id})" style="margin-left:4px;">Resolve</button>` : ''}
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load support tickets', e);
    }
}

async function chatWithTicketUser(phone) {
    // Navigate to the chats panel and select this user.
    navigateTo('chats');
    await selectChat(phone);

    // Suggest toggling human chat mode so the AI doesn't interfere.
    try {
        const res = await fetch(`${BASE_URL}/chats/${phone}/messages`);
        if (res.ok) {
            const data = await res.json();
            if (!data.user.is_human_chat) {
                if (confirm(
                    'This user currently has the AI bot active.\n\n' +
                    'Would you like to switch to HUMAN AGENT mode? ' +
                    'This prevents the bot from auto-replying while you chat with the user.'
                )) {
                    await fetch(`${BASE_URL}/chats/${phone}/toggle-human`, { method: 'POST' });
                    loadActiveChatHistory();
                    loadChatThreads(getSelectedLocation());
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}
window.chatWithTicketUser = chatWithTicketUser;

async function resolveTicket(id) {
    if (!confirm('Mark this support ticket as Resolved?')) return;
    try {
        const res = await fetch(`${BASE_URL}/tickets/${id}/resolve`, { method: 'POST' });
        if (res.ok) {
            alert('Ticket resolved successfully!');
            loadTickets(getSelectedLocation());
        }
    } catch (e) {
        console.error(e);
    }
}
window.resolveTicket = resolveTicket;

// --- Admins ---
async function loadAdmins() {
    try {
        const res = await fetch(`${BASE_URL}/users`);
        const admins = await res.json();

        const tbody = document.getElementById('tbl-admins');
        tbody.innerHTML = '';

        admins.forEach(a => {
            tbody.innerHTML += `
                <tr>
                    <td><strong>${escapeHTML(a.username)}</strong></td>
                    <td>${a.role === 'super_admin' ? 'Super Admin' : 'Branch Admin'}</td>
                    <td>${escapeHTML(a.location || 'All Locations')}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" title="Edit Admin" onclick="editAdmin(${a.id})"><i class="fa-solid fa-edit"></i></button>
                        <button class="btn btn-warning btn-sm" title="Force Password Reset" onclick="forceResetAdmin(${a.id}, '${escapeHTML(a.username)}')"><i class="fa-solid fa-key"></i></button>
                        <button class="btn btn-danger btn-sm" title="Delete Admin" onclick="deleteAdmin(${a.id})"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });
    } catch (e) {
        console.error('Failed to load admins', e);
    }
}

// Default chart colors used as fallback when the API is unreachable.
const DEFAULT_COLORS = ['#c62828', '#1a237e', '#f59e0b', '#10b981', '#8b5cf6', '#a855f7'];

// --- Chat Analysis (Lead CRM) ---
async function loadChatAnalysisTab() {
    try {
        const res = await fetch(`${BASE_URL}/chats`);
        if (!res.ok) throw new Error('Failed to fetch leads');
        const leads = await res.json();
        state.crmLeadsList = leads;
        renderCrmLeads();
    } catch (e) {
        console.error('Error fetching leads:', e);
        document.getElementById('crm-leads-list').innerHTML = `<div class="placeholder-text">Failed to load leads.</div>`;
    }
}

function renderCrmLeads() {
    const listEl = document.getElementById('crm-leads-list');
    const filter = document.getElementById('filter-lead-status').value;
    
    listEl.innerHTML = '';
    
    const filteredLeads = state.crmLeadsList.filter(l => {
        if (filter === 'all') return true;
        const status = l.lead_status || 'unassigned';
        return status === filter;
    });
    
    if (filteredLeads.length === 0) {
        listEl.innerHTML = `<div class="placeholder-text">No leads match this filter.</div>`;
        return;
    }
    
    filteredLeads.forEach(lead => {
        const div = document.createElement('div');
        div.className = `thread-item ${state.activeCrmPhone === lead.phone_number ? 'active' : ''}`;
        
        let icon = '';
        if (lead.lead_status === 'hot') icon = '🔥';
        else if (lead.lead_status === 'warm') icon = '🟡';
        else if (lead.lead_status === 'cold') icon = '🧊';
        
        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; width:100%;">
                <strong>${lead.name || lead.phone_number} ${icon}</strong>
                <small style="color:var(--text-muted);">${formatRelativeTime(lead.last_message_time)}</small>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                ${lead.phone_number}
            </div>
        `;
        div.onclick = () => selectCrmLead(lead);
        listEl.appendChild(div);
    });
}

document.getElementById('filter-lead-status')?.addEventListener('change', renderCrmLeads);

async function selectCrmLead(lead) {
    state.activeCrmPhone = lead.phone_number;
    renderCrmLeads(); // update active state in list
    
    document.getElementById('crm-placeholder').style.display = 'none';
    document.getElementById('crm-main-header').style.display = 'flex';
    document.getElementById('crm-main-body').style.display = 'flex';
    
    document.getElementById('crm-user-name').textContent = lead.name || 'Unknown Name';
    document.getElementById('crm-user-phone').textContent = lead.phone_number;
    document.getElementById('crm-override-status').value = lead.lead_status || 'unassigned';
    
    // Display existing AI analysis if any
    const aiOutput = document.getElementById('crm-ai-output');
    if (lead.ai_analysis || lead.ai_next_steps) {
        aiOutput.style.display = 'block';
        document.getElementById('crm-ai-summary').textContent = lead.ai_analysis || 'No summary available.';
        
        const stepsContainer = document.getElementById('crm-ai-next-steps');
        stepsContainer.innerHTML = '';
        if (lead.ai_next_steps) {
            const steps = lead.ai_next_steps.split('\n').filter(s => s.trim());
            const ul = document.createElement('ul');
            ul.style.paddingLeft = '20px';
            ul.style.marginTop = '0';
            steps.forEach(s => {
                const li = document.createElement('li');
                li.textContent = s.replace(/^-/, '').trim();
                ul.appendChild(li);
            });
            stepsContainer.appendChild(ul);
        } else {
            stepsContainer.textContent = 'No next steps available.';
        }
    } else {
        aiOutput.style.display = 'none';
    }
    
    // Fetch and display chat history
    try {
        const res = await fetch(`${BASE_URL}/chats/${lead.phone_number}/messages`);
        if (res.ok) {
            const messages = await res.json();
            renderCrmChatHistory(messages);
        }
    } catch (e) {
        console.error('Failed to load CRM chat history', e);
    }
}

function renderCrmChatHistory(messages) {
    const container = document.getElementById('crm-chat-history');
    container.innerHTML = '';
    
    if (!messages || messages.length === 0) {
        container.innerHTML = `<div class="placeholder-text">No conversation history yet.</div>`;
        return;
    }
    
    messages.forEach(msg => {
        const isUser = msg.role === 'user';
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${isUser ? 'received' : 'sent'}`;
        bubble.innerHTML = `
            <div class="msg-content">${escapeHTML(msg.content)}</div>
            <div class="msg-time">${formatRelativeTime(msg.created_at)}</div>
        `;
        container.appendChild(bubble);
    });
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

document.getElementById('btn-crm-analyze')?.addEventListener('click', async () => {
    if (!state.activeCrmPhone) return;
    
    const btn = document.getElementById('btn-crm-analyze');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
    btn.disabled = true;
    
    try {
        const res = await fetch(`${BASE_URL}/leads/${state.activeCrmPhone}/analyze`, { method: 'POST' });
        if (!res.ok) throw new Error('Analysis failed');
        const data = await res.json();
        
        // Update local state
        const lead = state.crmLeadsList.find(l => l.phone_number === state.activeCrmPhone);
        if (lead) {
            lead.lead_status = data.lead_status;
            lead.ai_analysis = data.ai_analysis;
            lead.ai_next_steps = data.ai_next_steps;
        }
        
        // Re-render
        selectCrmLead(lead);
    } catch (e) {
        console.error(e);
        alert('Failed to analyze chat.');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
});

document.getElementById('crm-override-status')?.addEventListener('change', async (e) => {
    if (!state.activeCrmPhone) return;
    const newStatus = e.target.value;
    
    try {
        const res = await fetch(`${BASE_URL}/leads/${state.activeCrmPhone}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (res.ok) {
            const lead = state.crmLeadsList.find(l => l.phone_number === state.activeCrmPhone);
            if (lead) lead.lead_status = newStatus;
            renderCrmLeads();
        }
    } catch (err) {
        console.error('Failed to override status', err);
    }
});

document.getElementById('btn-crm-go-live')?.addEventListener('click', async () => {
    if (!state.activeCrmPhone) return;
    const phone = state.activeCrmPhone;
    
    // Switch to chats tab
    document.querySelector('.menu-item[data-tab="chats"]')?.click();
    
    // Poll to select chat once loaded
    let retries = 0;
    const interval = setInterval(() => {
        const chatThread = document.querySelector(`.chat-thread[onclick="selectChat('${phone}')"]`);
        if (chatThread) {
            clearInterval(interval);
            selectChat(phone);
        }
        retries++;
        if (retries > 20) clearInterval(interval); // Timeout after 2s
    }, 100);
});


// ==========================================
// RAG & AI Agent Tools Orchestrator
// ==========================================
async function loadRAGTab() {
    await loadRAGStatus();
    await loadRegisteredTools();
}

async function loadRAGStatus() {
    try {
        const res = await fetch(`${BASE_URL}/rag/status`);
        const status = await res.json();

        document.getElementById('rag-indexed-chunks').textContent = `${status.count || 0} Chunks`;
        const statusEl = document.getElementById('rag-embeddings-status');
        if (status.embeddings_active) {
            statusEl.textContent = 'Active';
            statusEl.className = 'badge';
            statusEl.style.background = '#e8f5e9';
            statusEl.style.color = '#2e7d32';
        } else {
            statusEl.textContent = 'Inactive';
            statusEl.className = 'badge';
            statusEl.style.background = '#ffebee';
            statusEl.style.color = '#c62828';
        }
    } catch (e) {
        console.error('Failed to RAG stats status', e);
    }
}

async function rebuildRAGIndex() {
    const btn = document.getElementById('btn-reindex-rag');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i> Rebuilding...';
    try {
        const res = await fetch(`${BASE_URL}/rag/rebuild`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            alert(`RAG vector index rebuilt successfully! Total chunks: ${data.count}`);
            loadRAGStatus();
            loadKnowledgeStats(); // sync counts
        } else {
            const err = await res.json();
            alert(`Rebuild failed: ${err.detail}`);
        }
    } catch (e) {
        console.error(e);
        alert('Server error rebuilding index.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function testRAGQuery() {
    const queryInput = document.getElementById('rag-test-query');
    const query = queryInput.value.trim();
    if (!query) return;

    const btn = document.getElementById('btn-search-rag');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

    const resultsEl = document.getElementById('rag-test-results');
    resultsEl.textContent = 'Searching...';
    resultsEl.classList.remove('placeholder-text');

    try {
        const res = await fetch(`${BASE_URL}/rag/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        if (res.ok) {
            const data = await res.json();
            if (!data.context || data.context.trim() === '') {
                resultsEl.textContent = 'No relevant context retrieved.';
            } else {
                resultsEl.textContent = data.context;
            }
        } else {
            const err = await res.json();
            resultsEl.textContent = `Error: ${err.detail}`;
        }
    } catch (e) {
        console.error(e);
        resultsEl.textContent = 'Connection error.';
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

let registeredToolsCache = [];

async function loadRegisteredTools() {
    try {
        const res = await fetch(`${BASE_URL}/tools`);
        const tools = await res.json();
        registeredToolsCache = tools;

        const selectEl = document.getElementById('rag-tool-select');
        selectEl.innerHTML = '<option value="">-- Select a tool to inspect --</option>';

        tools.forEach(t => {
            selectEl.innerHTML += `<option value="${t.name}">${t.name}</option>`;
        });

        document.getElementById('rag-tool-details').classList.add('hide');
        document.getElementById('rag-tool-tester-form').classList.add('hide');
    } catch (e) {
        console.error('Failed to load registered tools', e);
    }
}

function handleToolSelect(toolName) {
    const detailsEl = document.getElementById('rag-tool-details');
    const testerEl = document.getElementById('rag-tool-tester-form');

    if (!toolName) {
        detailsEl.classList.add('hide');
        testerEl.classList.add('hide');
        return;
    }

    const tool = registeredToolsCache.find(t => t.name === toolName);
    if (!tool) return;

    document.getElementById('rag-tool-name').textContent = tool.name;
    document.getElementById('rag-tool-description').textContent = tool.description;

    const paramsList = document.getElementById('rag-tool-params-list');
    paramsList.innerHTML = '';

    const inputsContainer = document.getElementById('tool-call-arguments-inputs');
    inputsContainer.innerHTML = '';

    // Clear tool call output
    document.getElementById('tool-call-output').textContent = '';

    const props = tool.parameters?.properties || {};
    const required = tool.parameters?.required || [];

    for (const [propName, propDetails] of Object.entries(props)) {
        const isRequired = required.includes(propName);
        const reqMark = isRequired ? '<span style="color:var(--danger)">*</span>' : '';

        // List parameter details
        paramsList.innerHTML += `
            <li>
                <strong>${propName}</strong> (${propDetails.type})${reqMark}: 
                <span class="text-muted">${propDetails.description || ''}</span>
            </li>
        `;

        // Create form field for this parameter
        let inputHtml = '';
        if (propDetails.type === 'boolean') {
            inputHtml = `
                <div style="display:flex; align-items:center; gap:8px;">
                    <input type="checkbox" id="tool-arg-${propName}" name="${propName}" style="width:auto;">
                    <label for="tool-arg-${propName}" style="margin:0; font-weight:normal;">${propDetails.description || propName}</label>
                </div>
            `;
        } else if (propDetails.type === 'integer' || propDetails.type === 'number') {
            inputHtml = `
                <label for="tool-arg-${propName}" style="font-size:12px; font-weight:500;">${propName} (${propDetails.type})${reqMark}</label>
                <input type="number" id="tool-arg-${propName}" name="${propName}" ${isRequired ? 'required' : ''} placeholder="${propDetails.description || ''}" style="width:100%; border:1px solid var(--border-color); padding:8px 12px; border-radius:8px; background: #f8f9fc;">
            `;
        } else {
            // string or default
            inputHtml = `
                <label for="tool-arg-${propName}" style="font-size:12px; font-weight:500;">${propName}${reqMark}</label>
                <input type="text" id="tool-arg-${propName}" name="${propName}" ${isRequired ? 'required' : ''} placeholder="${propDetails.description || ''}" style="width:100%; border:1px solid var(--border-color); padding:8px 12px; border-radius:8px; background: #f8f9fc;">
            `;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'input-group';
        wrapper.innerHTML = inputHtml;
        inputsContainer.appendChild(wrapper);
    }

    detailsEl.classList.remove('hide');
    testerEl.classList.remove('hide');
}

async function handleToolCallSubmit(e) {
    e.preventDefault();
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalHtml = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Invoking...';
    }

    const toolName = document.getElementById('rag-tool-select').value;
    const tool = registeredToolsCache.find(t => t.name === toolName);
    if (!tool) {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
        return;
    }

    const props = tool.parameters?.properties || {};
    const argumentsObj = {};

    for (const [propName, propDetails] of Object.entries(props)) {
        const inputEl = document.getElementById(`tool-arg-${propName}`);
        if (!inputEl) continue;

        if (propDetails.type === 'boolean') {
            argumentsObj[propName] = inputEl.checked;
        } else if (propDetails.type === 'integer') {
            const val = parseInt(inputEl.value);
            if (!isNaN(val)) argumentsObj[propName] = val;
        } else if (propDetails.type === 'number') {
            const val = parseFloat(inputEl.value);
            if (!isNaN(val)) argumentsObj[propName] = val;
        } else {
            const val = inputEl.value.trim();
            if (val !== '') argumentsObj[propName] = val;
        }
    }

    const outputEl = document.getElementById('tool-call-output');
    outputEl.textContent = 'Executing tool...';

    try {
        const res = await fetch(`${BASE_URL}/tools/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: toolName,
                arguments: argumentsObj
            })
        });

        const data = await res.json();
        outputEl.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
        console.error(err);
        outputEl.textContent = `Execution failed: ${err.message}`;
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    }
}

// ==========================================
// Actions & Forms Submit Handlers
// ==========================================
function setupEventListeners() {
    // Message Analytics Filter Setup
    const filterStart = document.getElementById('msg-filter-start');
    const filterEnd = document.getElementById('msg-filter-end');
    if (filterStart && filterEnd) {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7);
        filterEnd.value = today.toISOString().split('T')[0];
        filterStart.value = lastWeek.toISOString().split('T')[0];
    }
    const msgForm = document.getElementById('msg-analytics-form');
    if (msgForm) msgForm.addEventListener('submit', loadMessageAnalytics);

    // Registration Analytics Filter Setup
    const filterRegStart = document.getElementById('reg-filter-start');
    const filterRegEnd = document.getElementById('reg-filter-end');
    if (filterRegStart && filterRegEnd) {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7);
        filterRegEnd.value = today.toISOString().split('T')[0];
        filterRegStart.value = lastWeek.toISOString().split('T')[0];
    }
    const regForm = document.getElementById('reg-analytics-form');
    if (regForm) regForm.addEventListener('submit', loadRegistrationAnalytics);

    const filterRegStartPage = document.getElementById('reg-filter-start-page');
    const filterRegEndPage = document.getElementById('reg-filter-end-page');
    if (filterRegStartPage && filterRegEndPage) {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7);
        filterRegEndPage.value = today.toISOString().split('T')[0];
        filterRegStartPage.value = lastWeek.toISOString().split('T')[0];
    }
    const regFormPage = document.getElementById('reg-analytics-form-page');
    if (regFormPage) regFormPage.addEventListener('submit', loadRegistrationAnalyticsPage);


    // Ticket Analytics Filter Setup
    const filterTicketStart = document.getElementById('ticket-filter-start-page');
    const filterTicketEnd = document.getElementById('ticket-filter-end-page');
    if (filterTicketStart && filterTicketEnd) {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7);
        filterTicketEnd.value = today.toISOString().split('T')[0];
        filterTicketStart.value = lastWeek.toISOString().split('T')[0];
    }
    const ticketFormPage = document.getElementById('ticket-analytics-form-page');
    if (ticketFormPage) ticketFormPage.addEventListener('submit', loadTicketAnalyticsPage);

    // Nav Click Router
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.getAttribute('data-tab');
            navigateTo(tabId);
        });
    });

    // Branch Selector Reload
    document.getElementById('location-select').addEventListener('change', () => {
        loadPageData(state.currentPage);
    });

    // Login Form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Logging in...';

        const usernameInput = document.getElementById('username').value;
        const passwordInput = document.getElementById('password').value;
        const errorEl = document.getElementById('login-error');

        errorEl.classList.add('hide');

        try {
            const res = await fetch(`${BASE_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: usernameInput, password: passwordInput })
            });

            if (res.ok) {
                const adminData = await res.json();
                if (adminData.require_password_reset) {
                    state.tempResetToken = adminData.temp_token;
                    document.getElementById('login-container').classList.remove('active');
                    document.getElementById('reset-password-container').classList.remove('hide');
                    document.getElementById('reset-password-container').classList.add('active');
                } else {
                    loginSuccess(adminData);
                }
            } else {
                const err = await res.json();
                errorEl.textContent = err.detail || 'Authentication failed';
                errorEl.classList.remove('hide');
            }
        } catch (err) {
            errorEl.textContent = 'Server connection failed';
            errorEl.classList.remove('hide');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Reset Password Form
    document.getElementById('reset-password-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';

        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        const errorEl = document.getElementById('reset-error');
        errorEl.classList.add('hide');

        if (newPassword !== confirmPassword) {
            errorEl.textContent = 'Passwords do not match';
            errorEl.classList.remove('hide');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
            return;
        }

        try {
            const res = await fetch(`${BASE_URL}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ temp_token: state.tempResetToken, new_password: newPassword })
            });

            if (res.ok) {
                const adminData = await res.json();
                document.getElementById('reset-password-container').classList.remove('active');
                document.getElementById('reset-password-container').classList.add('hide');
                loginSuccess(adminData);
            } else {
                const err = await res.json();
                errorEl.textContent = err.detail || 'Password reset failed';
                errorEl.classList.remove('hide');
            }
        } catch (err) {
            errorEl.textContent = 'Server connection failed';
            errorEl.classList.remove('hide');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Logout Button
    document.getElementById('btn-logout').addEventListener('click', async () => {
        await fetch(`${BASE_URL}/auth/logout`, { method: 'POST' });
        showLoginScreen();
    });

    // AI Marketing Insights Generate
    document.getElementById('btn-generate-insights').addEventListener('click', async () => {
        const btn = document.getElementById('btn-generate-insights');
        const placeholder = document.getElementById('insights-placeholder');
        const content = document.getElementById('insights-content');

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';
        placeholder.innerHTML = '<p><i class="fa-solid fa-brain animate-pulse"></i> Gemini AI is compiling message histories and generating reports...</p>';
        placeholder.classList.remove('hide');
        content.classList.add('hide');

        try {
            const res = await fetch(`${BASE_URL}/insights/generate`);
            if (res.ok) {
                const text = await res.json();
                placeholder.classList.add('hide');
                content.textContent = text;
                content.classList.remove('hide');
            } else {
                placeholder.innerHTML = '<p class="text-red">Failed to generate insights. Please try again.</p>';
            }
        } catch (e) {
            placeholder.innerHTML = '<p class="text-red">Server error generating insights.</p>';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Compile';
        }
    });

    // Chat Interactive: Human-Chat Toggle
    document.getElementById('btn-toggle-human').addEventListener('click', async () => {
        if (!state.activeChatPhone) return;
        try {
            const res = await fetch(`${BASE_URL}/chats/${state.activeChatPhone}/toggle-human`, { method: 'POST' });
            if (res.ok) {
                loadActiveChatHistory();
                loadChatThreads(getSelectedLocation());
            }
        } catch (e) {
            console.error(e);
        }
    });

    // Chat Interactive: Reset Session
    document.getElementById('btn-reset-session').addEventListener('click', async () => {
        if (!state.activeChatPhone || !confirm('Resetting the AI context will clear the agent conversation memory for this session. Proceed?')) return;
        try {
            const res = await fetch(`${BASE_URL}/chats/${state.activeChatPhone}/reset-session`, { method: 'POST' });
            if (res.ok) {
                alert('AI Session cleared successfully!');
                loadActiveChatHistory();
            }
        } catch (e) {
            console.error(e);
        }
    });

    // Chat Interactive: Send Message
    const sendMsgFunc = async () => {
        const input = document.getElementById('chat-input');
        const btn = document.getElementById('btn-send-message');
        const text = input.value.trim();
        if (!text || !state.activeChatPhone) return;

        setButtonLoading(btn, true);
        try {
            const res = await fetch(`${BASE_URL}/chats/${state.activeChatPhone}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            if (res.ok) {
                input.value = '';
                loadActiveChatHistory();
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail || 'Could not send message'}`);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setButtonLoading(btn, false);
        }
    };

    document.getElementById('btn-send-message').addEventListener('click', sendMsgFunc);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMsgFunc();
    });

    // Chat Interactive: Analyze Chat
    function formatAnalysisReport(text) {
        if (!text) return '';

        const intentLabel = 'Customer Intent:';
        const sentimentLabel = 'Sentiment & Obstacles:';
        const adviceLabel = 'Agent Action Advice:';

        const intentIdx = text.indexOf(intentLabel);
        const sentimentIdx = text.indexOf(sentimentLabel);
        const adviceIdx = text.indexOf(adviceLabel);

        if (intentIdx === -1 || sentimentIdx === -1 || adviceIdx === -1) {
            // Fallback: strip double stars and return nicely formatted default box
            const cleanText = text.replace(/\*\*/g, '').replace(/\n/g, '<br>');
            return `<div class="analysis-box default-box">${cleanText}</div>`;
        }

        const intentText = text.substring(intentIdx + intentLabel.length, sentimentIdx).trim();
        const sentimentText = text.substring(sentimentIdx + sentimentLabel.length, adviceIdx).trim();
        const adviceText = text.substring(adviceIdx + adviceLabel.length).trim();

        let adviceHtml = '';
        const lines = adviceText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length > 0) {
            adviceHtml = '<ul class="analysis-bullets">';
            lines.forEach(line => {
                const cleanLine = line.replace(/^-\s*/, '').replace(/^\*\s*/, '');
                adviceHtml += `<li>${escapeHTML(cleanLine)}</li>`;
            });
            adviceHtml += '</ul>';
        } else {
            adviceHtml = `<p>${escapeHTML(adviceText)}</p>`;
        }

        return `
            <div class="analysis-container">
                <div class="analysis-box intent-box">
                    <div class="box-header"><i class="fa-solid fa-bullseye"></i> Customer Intent</div>
                    <div class="box-body"><p>${escapeHTML(intentText)}</p></div>
                </div>
                
                <div class="analysis-box sentiment-box">
                    <div class="box-header"><i class="fa-solid fa-face-smile"></i> Sentiment & Obstacles</div>
                    <div class="box-body"><p>${escapeHTML(sentimentText)}</p></div>
                </div>
                
                <div class="analysis-box advice-box">
                    <div class="box-header"><i class="fa-solid fa-handshake-angle"></i> Agent Action Advice</div>
                    <div class="box-body">${adviceHtml}</div>
                </div>
            </div>
        `;
    }

    document.getElementById('btn-analyze-chat').addEventListener('click', async () => {
        if (!state.activeChatPhone) return;

        const loadingEl = document.getElementById('chat-analysis-loading');
        const contentEl = document.getElementById('chat-analysis-content');

        // Reset and open the modal
        loadingEl.classList.remove('hide');
        contentEl.classList.add('hide');
        contentEl.innerHTML = '';
        openModal('modal-chat-analysis');

        try {
            const res = await fetch(`${BASE_URL}/chats/${state.activeChatPhone}/analyze`);
            if (res.ok) {
                const text = await res.json();
                loadingEl.classList.add('hide');
                contentEl.classList.remove('hide');
                contentEl.innerHTML = formatAnalysisReport(text);
            } else {
                loadingEl.classList.add('hide');
                contentEl.classList.remove('hide');
                contentEl.innerHTML = '<span style="color:var(--primary);">Failed to analyze chat log. The conversation may be too short.</span>';
            }
        } catch (e) {
            loadingEl.classList.add('hide');
            contentEl.classList.remove('hide');
            contentEl.innerHTML = '<span style="color:var(--primary);">Server error. Please try again later.</span>';
        }
    });

    // Chat Interactive: Export Chat Logs
    document.getElementById('btn-export-chat').addEventListener('click', () => {
        if (!state.activeChatPhone) return;
        window.open(`${BASE_URL}/chats/${state.activeChatPhone}/export`);
    });

    // Broadcast Form
    document.getElementById('broadcast-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        setButtonLoading(submitBtn, true);

        const target = document.getElementById('broadcast-target').value;
        const msg = document.getElementById('broadcast-message').value.trim();

        const isBranchAdmin = state.user && state.user.role === 'branch_admin';
        const body = { target, message: msg };

        if (target === 'branch') {
            let checkedBranches = [];
            if (isBranchAdmin) {
                checkedBranches = [state.user.location];
            } else {
                const branchList = document.getElementById('broadcast-branches-list');
                checkedBranches = Array.from(branchList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
                if (checkedBranches.length === 0) {
                    alert('Please select at least one branch.');
                    setButtonLoading(submitBtn, false);
                    return;
                }
            }
            body.locations = checkedBranches;
        } else if (target === 'package') {
            const packageList = document.getElementById('broadcast-packages-list');
            const checkedPackages = Array.from(packageList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => parseInt(cb.value, 10));
            if (checkedPackages.length === 0) {
                alert('Please select at least one package.');
                setButtonLoading(submitBtn, false);
                return;
            }
            body.package_ids = checkedPackages;
        } else if (target === 'package_branch') {
            let checkedBranches = [];
            if (isBranchAdmin) {
                checkedBranches = [state.user.location];
            } else {
                const branchList = document.getElementById('broadcast-branches-list');
                checkedBranches = Array.from(branchList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
            }
            const packageList = document.getElementById('broadcast-packages-list');
            const checkedPackages = Array.from(packageList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => parseInt(cb.value, 10));
            
            if (checkedBranches.length === 0 || checkedPackages.length === 0) {
                alert('Please select at least one branch and at least one package.');
                setButtonLoading(submitBtn, false);
                return;
            }
            body.locations = checkedBranches;
            body.package_ids = checkedPackages;
        }

        try {
            const res = await fetch(`${BASE_URL}/broadcast`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (res.ok) {
                alert('Broadcast queued for sending!');
                document.getElementById('broadcast-message').value = '';
                document.getElementById('broadcast-target').value = isBranchAdmin ? 'branch' : 'all';
                document.getElementById('broadcast-target').dispatchEvent(new Event('change'));
                loadBroadcastHistory();
            } else {
                const err = await res.json();
                alert(`Failed to send broadcast: ${err.detail}`);
            }
        } catch (e) {
            console.error(e);
            alert('Server connection failed.');
        } finally {
            setButtonLoading(submitBtn, false);
        }
    });

    // Clients Page Filters
    document.getElementById('filter-client-location').addEventListener('change', loadRegisteredClients);
    document.getElementById('filter-client-search').addEventListener('input', debounce(loadRegisteredClients, 400));
    document.getElementById('btn-send-clients-msg').addEventListener('click', () => openSendMessageModal('clients'));

    // Bookings Page Filters
    document.getElementById('filter-booking-location').addEventListener('change', loadBookings);
    document.getElementById('filter-booking-status').addEventListener('change', loadBookings);
    document.getElementById('filter-booking-package').addEventListener('change', loadBookings);
    document.getElementById('filter-booking-start-date').addEventListener('change', loadBookings);
    document.getElementById('filter-booking-end-date').addEventListener('change', loadBookings);
    document.getElementById('filter-booking-search').addEventListener('input', debounce(loadBookings, 400));
    document.getElementById('btn-send-bookings-msg').addEventListener('click', () => openSendMessageModal('bookings'));

    // Edit Booking Form Submission
    document.getElementById('booking-edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('booking-edit-id').value;
        const payload = {
            package_id: parseInt(document.getElementById('booking-edit-package').value),
            status: document.getElementById('booking-edit-status').value,
            name: document.getElementById('booking-edit-name').value,
            dob: document.getElementById('booking-edit-dob').value,
            ghana_card: document.getElementById('booking-edit-ghanacard').value,
            place_of_birth: document.getElementById('booking-edit-birthplace').value,
            witness_name: document.getElementById('booking-edit-witnessname').value,
            witness_phone: document.getElementById('booking-edit-witnessphone').value,
            marital_status: document.getElementById('booking-edit-marital').value,
            location: document.getElementById('booking-edit-location').value
        };

        try {
            const res = await fetch(`${BASE_URL}/registrations/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                closeModal('modal-booking');
                loadBookings();
            } else {
                const err = await res.json();
                alert(`Failed to save booking: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving booking.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Edit Ticket Form Submission
    document.getElementById('ticket-edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('ticket-edit-id').value;
        const payload = {
            subject: document.getElementById('ticket-edit-subject').value,
            description: document.getElementById('ticket-edit-desc').value,
            location: document.getElementById('ticket-edit-location').value || null,
            status: document.getElementById('ticket-edit-status').value
        };

        try {
            const res = await fetch(`${BASE_URL}/tickets/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                closeModal('modal-ticket');
                loadTickets(getSelectedLocation());
            } else {
                const err = await res.json();
                alert(`Failed to save ticket: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving ticket.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Select-all logic for clients
    const checkAllClients = document.getElementById('check-all-clients');
    if (checkAllClients) {
        checkAllClients.addEventListener('change', (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.check-client').forEach(cb => {
                cb.checked = checked;
            });
            updateClientCheckboxState();
        });
    }

    // Select-all logic for bookings
    const checkAllBookings = document.getElementById('check-all-bookings');
    if (checkAllBookings) {
        checkAllBookings.addEventListener('change', (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.check-booking').forEach(cb => {
                cb.checked = checked;
            });
            updateBookingCheckboxState();
        });
    }

    // Send Message Modal Form (direct messaging)
    document.getElementById('send-message-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';

        const idsData = JSON.parse(document.getElementById('send-msg-ids').value);
        const mode = document.getElementById('send-msg-mode').value;
        const message = document.getElementById('send-msg-text').value.trim();

        if (!message || idsData.length === 0) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
            return;
        }

        try {
            if (mode === 'bookings') {
                const regIds = idsData.map(d => d.id).filter(Boolean);
                const res = await fetch(`${BASE_URL}/registrations/send`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ registration_ids: regIds, message: message })
                });
                if (res.ok) {
                    const data = await res.json();
                    alert(`Message queued for ${data.recipient_count} recipient(s)!`);
                    closeModal('modal-send-message');
                    loadBookings();
                } else {
                    const err = await res.json();
                    alert(`Failed: ${err.detail}`);
                }
            } else if (mode === 'clients') {
                const phones = idsData.map(d => d.phone);
                let sent = 0;
                for (const phone of phones) {
                    try {
                        const userRes = await fetch(`${BASE_URL}/chats/${phone}/messages`);
                        if (userRes.ok) {
                            await fetch(`${BASE_URL}/chats/${phone}/send`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ message: message })
                            });
                            sent++;
                        }
                    } catch (err) {
                        console.error(`Failed to send to ${phone}`, err);
                    }
                }
                alert(`Message sent to ${sent}/${phones.length} recipient(s)!`);
                closeModal('modal-send-message');
                loadRegisteredClients();
            }
        } catch (err) {
            console.error('Failed to send messages', err);
            alert('Server error sending messages.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Modal Close Triggers
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            closeModal(btn.getAttribute('data-modal'));
        });
    });

    // Add triggers for modals
    document.getElementById('btn-add-package').addEventListener('click', () => {
        document.getElementById('package-form').reset();
        document.getElementById('package-id').value = '';
        document.getElementById('package-modal-title').textContent = 'Add Lesson Package';
        openModal('modal-package');
    });

    document.getElementById('btn-add-branch').addEventListener('click', () => {
        document.getElementById('client-form').reset();
        document.getElementById('client-id').value = '';
        document.getElementById('client-modal-title').textContent = 'Add Branch Office';
        openModal('modal-client');
    });

    document.getElementById('btn-add-admin').addEventListener('click', () => {
        document.getElementById('admin-form').reset();
        document.getElementById('admin-id').value = '';
        document.getElementById('admin-password-group').classList.remove('hide');
        document.getElementById('admin-user-password').required = true;
        document.getElementById('admin-modal-title').textContent = 'Add Admin Account';
        openModal('modal-admin');
    });

    document.getElementById('btn-add-fee').addEventListener('click', () => {
        document.getElementById('fee-form').reset();
        document.getElementById('fee-id').value = '';
        document.getElementById('fee-mandatory').checked = false;
        document.getElementById('fee-pass-through').checked = false;
        document.getElementById('fee-modal-title').textContent = 'Add Checkout Fee';
        openModal('modal-fee');
    });

    // PDF Vector database File upload listener
    const pdfFileInput = document.getElementById('pdf-file-input');
    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const statusEl = document.getElementById('upload-status');
            statusEl.innerHTML = '<span style="color:var(--primary);"><i class="fa-solid fa-spinner fa-spin"></i> Ingesting PDF into ChromaDB...</span>';

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch(`${BASE_URL}/documents/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    alert(`Successfully ingested PDF: Chunks created: ${data.chunks_created}`);
                    statusEl.innerHTML = '<span style="color:#2e7d32;">Upload and ingestion complete!</span>';
                    loadKnowledgeStats();
                    loadDocumentsList();
                    loadRAGStatus(); // sync counts
                } else {
                    const err = await response.json();
                    alert(`Ingestion failed: ${err.detail}`);
                    statusEl.innerHTML = '<span style="color:var(--primary);">Ingestion failed.</span>';
                }
            } catch (e) {
                alert('Upload connection failed');
                statusEl.innerHTML = '<span style="color:var(--primary);">Connection error.</span>';
            } finally {
                e.target.value = '';
            }
        });
    }

    // Q&A manual entry form submission
    document.getElementById('knowledge-manual-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('btn-kb-manual-submit');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('kb-manual-id').value;
        const payload = {
            topic: document.getElementById('kb-manual-topic').value,
            content: document.getElementById('kb-manual-content').value
        };

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${BASE_URL}/knowledge/${id}` : `${BASE_URL}/knowledge`;

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                document.getElementById('knowledge-manual-form').reset();
                document.getElementById('kb-manual-id').value = '';
                submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Entry';
                loadKnowledgeBase();
            } else {
                const err = await res.json();
                alert(`Failed to save Q&A: ${err.detail}`);
            }
        } catch (err) {
            alert('Network error saving Q&A.');
        } finally {
            submitBtn.disabled = false;
            if (submitBtn.innerHTML.includes('fa-spinner')) {
                submitBtn.innerHTML = originalHtml;
            }
        }
    });



    // CRUD forms submit bindings
    document.getElementById('package-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('package-id').value;
        const payload = {
            name: document.getElementById('package-name').value,
            category: document.getElementById('package-category').value,
            description: document.getElementById('package-desc').value,
            schedule_type: document.getElementById('package-schedule-type').value,
            duration_weeks: document.getElementById('package-duration-weeks').value,
            price: parseFloat(document.getElementById('package-price').value)
        };

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${BASE_URL}/packages/${id}` : `${BASE_URL}/packages`;

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeModal('modal-package');
                loadPackages();
            } else {
                const err = await res.json();
                alert(`Failed to save package: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving package.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    document.getElementById('client-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('client-id').value;
        const payload = {
            name: document.getElementById('client-name').value,
            region: document.getElementById('client-region').value,
            address: document.getElementById('client-address').value,
            contact_numbers: document.getElementById('client-contact-numbers').value,
            google_maps_link: document.getElementById('client-maps-link').value
        };

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${BASE_URL}/clients/${id}` : `${BASE_URL}/clients`;

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeModal('modal-client');
                loadBranches();
            } else {
                const err = await res.json();
                alert(`Failed to save branch: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving branch.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    document.getElementById('fee-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('fee-id').value;
        const payload = {
            name: document.getElementById('fee-name').value,
            description: document.getElementById('fee-desc').value,
            amount: parseFloat(document.getElementById('fee-amount').value),
            mandatory: document.getElementById('fee-mandatory').checked,
            pass_through: document.getElementById('fee-pass-through').checked
        };

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${BASE_URL}/fees/${id}` : `${BASE_URL}/fees`;

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeModal('modal-fee');
                loadAddonFees();
            } else {
                const err = await res.json();
                alert(`Failed to save fee: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving fee.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    document.getElementById('admin-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const id = document.getElementById('admin-id').value;
        const payload = {
            username: document.getElementById('admin-user-username').value,
            role: document.getElementById('admin-user-role').value,
            location: document.getElementById('admin-user-location').value || null
        };

        if (!id || document.getElementById('admin-user-password').value) {
            payload.password = document.getElementById('admin-user-password').value;
        }

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${BASE_URL}/users/${id}` : `${BASE_URL}/users`;

        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeModal('modal-admin');
                loadAdmins();
            } else {
                const err = await res.json();
                alert(`Failed to save admin: ${err.detail}`);
            }
        } catch (err) {
            console.error(err);
            alert('Server error saving admin.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // Chat Analysis Deep Report Generate
    document.getElementById('btn-generate-deep-analysis').addEventListener('click', async () => {
        const btn = document.getElementById('btn-generate-deep-analysis');
        const box = document.getElementById('deep-analysis-report-box');

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Regenerating Report...';
        box.innerHTML = '<p style="text-align:center; padding: 30px;"><i class="fa-solid fa-brain animate-pulse" style="font-size:32px;"></i> Gemini AI is clustering customer messages and compiling the semantic analytics report...</p>';

        try {
            const res = await fetch(`${BASE_URL}/insights/generate`);
            if (res.ok) {
                const text = await res.json();
                box.textContent = text;
            } else {
                box.textContent = 'Failed to generate semantic clustering report.';
            }
        } catch (e) {
            box.textContent = 'Server communication failed.';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Regenerate Report';
        }
    });

    // Consolidated Resources: Sub-tab selectors
    document.querySelectorAll('.resources-sub-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const subtab = btn.getAttribute('data-subtab');
            
            // Toggle active button style
            document.querySelectorAll('.resources-sub-tab').forEach(b => {
                b.classList.remove('btn-primary');
                b.classList.add('btn-secondary');
            });
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');

            // Toggle active sub-panel
            document.querySelectorAll('.resources-sub-panel').forEach(panel => {
                if (panel.id === `sub-panel-${subtab}`) {
                    panel.classList.remove('hide');
                } else {
                    panel.classList.add('hide');
                }
            });

            // Re-apply search filter for the newly active panel
            filterResourcesData();
        });
    });

    // Consolidated Resources: Search box
    const resourcesSearchInput = document.getElementById('resources-search');
    if (resourcesSearchInput) {
        resourcesSearchInput.addEventListener('input', debounce(() => {
            filterResourcesData();
        }, 300));
    }
}

// --- CRUD Actions ---
function openModal(id) {
    document.getElementById(id).classList.add('active');
}
function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

// Helper to prevent branch admin edit actions
function checkBranchAdminPermission() {
    if (state.user && state.user.role === 'branch_admin') {
        alert('Permission Denied: Branch Admins cannot perform edit or delete actions.');
        return true;
    }
    return false;
}

// Package edit/delete
async function editPackage(id) {
    if (checkBranchAdminPermission()) return;
    try {
        const res = await fetch(`${BASE_URL}/packages/${id}`);
        const p = await res.json();

        document.getElementById('package-id').value = p.id;
        document.getElementById('package-name').value = p.name;
        document.getElementById('package-category').value = p.category || 'Non-Students';
        document.getElementById('package-desc').value = p.description;
        document.getElementById('package-schedule-type').value = p.schedule_type || 'Combined';
        document.getElementById('package-duration-weeks').value = p.duration_weeks || '';
        document.getElementById('package-price').value = p.price;

        document.getElementById('package-modal-title').textContent = 'Edit Lesson Package';
        openModal('modal-package');
    } catch (e) { console.error(e); }
}
window.editPackage = editPackage;

async function deletePackage(id) {
    if (checkBranchAdminPermission()) return;
    if (!confirm('Are you sure you want to delete this package?')) return;
    const res = await fetch(`${BASE_URL}/packages/${id}`, { method: 'DELETE' });
    if (res.ok) loadPackages();
}
window.deletePackage = deletePackage;

// Client/Branch edit/delete
async function editClient(id) {
    if (checkBranchAdminPermission()) return;
    try {
        const res = await fetch(`${BASE_URL}/clients/${id}`);
        const c = await res.json();

        document.getElementById('client-id').value = c.id;
        document.getElementById('client-name').value = c.name;
        document.getElementById('client-region').value = c.region || '';
        document.getElementById('client-address').value = c.address || '';
        document.getElementById('client-contact-numbers').value = c.contact_numbers || '';
        document.getElementById('client-maps-link').value = c.google_maps_link || '';

        document.getElementById('client-modal-title').textContent = 'Edit Branch Office';
        openModal('modal-client');
    } catch (e) { console.error(e); }
}
window.editClient = editClient;

async function deleteClient(id) {
    if (checkBranchAdminPermission()) return;
    if (!confirm('Are you sure you want to delete this branch office?')) return;
    const res = await fetch(`${BASE_URL}/clients/${id}`, { method: 'DELETE' });
    if (res.ok) loadBranches();
}
window.deleteClient = deleteClient;

// Admin edit/delete
async function editAdmin(id) {
    try {
        const res = await fetch(`${BASE_URL}/users/${id}`);
        const a = await res.json();

        document.getElementById('admin-id').value = a.id;
        document.getElementById('admin-user-username').value = a.username;
        document.getElementById('admin-user-role').value = a.role;
        document.getElementById('admin-user-location').value = a.location || '';

        document.getElementById('admin-password-group').classList.add('hide'); // Hide password on edit
        document.getElementById('admin-user-password').required = false;
        document.getElementById('admin-modal-title').textContent = 'Edit Admin Account';
        openModal('modal-admin');
    } catch (e) { console.error(e); }
}
window.editAdmin = editAdmin;

async function deleteAdmin(id) {
    if (state.user && state.user.id === id) {
        alert('You cannot delete your own admin account.');
        return;
    }
    if (!confirm('Are you sure you want to delete this admin account?')) return;
    const res = await fetch(`${BASE_URL}/users/${id}`, { method: 'DELETE' });
    if (res.ok) loadAdmins();
}
window.deleteAdmin = deleteAdmin;

async function forceResetAdmin(id, username) {
    if (state.user && state.user.id === id) {
        alert('You cannot force-reset your own password this way. Use the edit feature.');
        return;
    }
    if (!confirm(`Are you sure you want to force a password reset for ${username}?\n\nThis will generate a temporary password that they must change upon next login.`)) return;

    try {
        const res = await fetch(`${BASE_URL}/users/${id}/force-reset`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            alert(`Password reset successful for ${username}.\n\nTEMPORARY PASSWORD: ${data.temp_password}\n\nPlease copy this and send it to the admin. They will be forced to change it on their next login.`);
        } else {
            alert('Failed to force password reset.');
        }
    } catch (e) {
        console.error(e);
        alert('Server error while resetting password.');
    }
}
window.forceResetAdmin = forceResetAdmin;

// Knowledge Base Q&A edit/delete
async function editKnowledge(id) {
    if (checkBranchAdminPermission()) return;
    try {
        const res = await fetch(`${BASE_URL}/knowledge/${id}`);
        const k = await res.json();

        document.getElementById('kb-manual-id').value = k.id;
        document.getElementById('kb-manual-topic').value = k.topic;
        document.getElementById('kb-manual-content').value = k.content;
        document.getElementById('btn-kb-manual-submit').innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Update Entry';

        // Scroll form into view
        document.getElementById('knowledge-manual-form').scrollIntoView({ behavior: 'smooth' });
    } catch (e) { console.error(e); }
}
window.editKnowledge = editKnowledge;

async function deleteKnowledge(id) {
    if (checkBranchAdminPermission()) return;
    if (!confirm('Are you sure you want to delete this knowledge record?')) return;
    const res = await fetch(`${BASE_URL}/knowledge/${id}`, { method: 'DELETE' });
    if (res.ok) loadKnowledgeBase();
}
window.deleteKnowledge = deleteKnowledge;

// Fee edit/delete
async function editFee(id) {
    if (checkBranchAdminPermission()) return;
    try {
        const res = await fetch(`${BASE_URL}/fees/${id}`);
        const f = await res.json();

        document.getElementById('fee-id').value = f.id;
        document.getElementById('fee-name').value = f.name;
        document.getElementById('fee-desc').value = f.description || '';
        document.getElementById('fee-amount').value = f.amount;
        document.getElementById('fee-mandatory').checked = !!f.mandatory;
        document.getElementById('fee-pass-through').checked = !!f.pass_through;

        document.getElementById('fee-modal-title').textContent = 'Edit Checkout Fee';
        openModal('modal-fee');
    } catch (e) { console.error(e); }
}
window.editFee = editFee;

async function deleteFee(id) {
    if (checkBranchAdminPermission()) return;
    if (!confirm('Are you sure you want to delete this fee?')) return;
    const res = await fetch(`${BASE_URL}/fees/${id}`, { method: 'DELETE' });
    if (res.ok) loadAddonFees();
}
window.deleteFee = deleteFee;

// Booking edit/delete CRUD
async function editBooking(id) {
    try {
        const res = await fetch(`${BASE_URL}/registrations/${id}`);
        const b = await res.json();

        document.getElementById('booking-edit-id').value = b.id;
        document.getElementById('booking-edit-package').value = b.package_id;
        document.getElementById('booking-edit-status').value = b.status || 'pending';
        document.getElementById('booking-edit-name').value = b.name || '';
        document.getElementById('booking-edit-dob').value = b.dob || '';
        document.getElementById('booking-edit-ghanacard').value = b.ghana_card || '';
        document.getElementById('booking-edit-birthplace').value = b.place_of_birth || '';
        document.getElementById('booking-edit-witnessname').value = b.witness_name || '';
        document.getElementById('booking-edit-witnessphone').value = b.witness_phone || '';
        document.getElementById('booking-edit-marital').value = b.marital_status || '';
        document.getElementById('booking-edit-location').value = b.location || '';

        openModal('modal-booking');
    } catch (e) { console.error(e); }
}
window.editBooking = editBooking;

async function deleteBooking(id) {
    if (!confirm('Are you sure you want to delete this registration booking?')) return;
    try {
        const res = await fetch(`${BASE_URL}/registrations/${id}`, { method: 'DELETE' });
        if (res.ok) {
            loadBookings();
        } else {
            const err = await res.json();
            alert(`Failed to delete booking: ${err.detail}`);
        }
    } catch (e) { console.error(e); }
}
window.deleteBooking = deleteBooking;

async function checkPayment(id) {
    try {
        const res = await fetch(`${BASE_URL}/registrations/${id}/check-payment`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            if (data.status === 'success') {
                alert(`Success: ${data.message}`);
                loadBookings();
                if (typeof loadOverview === 'function') loadOverview();
            } else if (data.status === 'pending') {
                alert(`Pending: ${data.message}`);
            } else {
                alert(`Error: ${data.message}`);
            }
        } else {
            alert(`Failed to check payment status: ${data.detail || 'Server error'}`);
        }
    } catch (e) {
        console.error(e);
        alert(`Network error: ${e.message}`);
    }
}
window.checkPayment = checkPayment;

// Ticket edit/delete CRUD
async function editTicket(id) {
    try {
        const res = await fetch(`${BASE_URL}/tickets/${id}`);
        const t = await res.json();

        document.getElementById('ticket-edit-id').value = t.id;
        document.getElementById('ticket-edit-subject').value = t.subject;
        document.getElementById('ticket-edit-desc').value = t.description || '';
        document.getElementById('ticket-edit-location').value = t.location || '';
        document.getElementById('ticket-edit-status').value = t.status || 'open';

        openModal('modal-ticket');
    } catch (e) { console.error(e); }
}
window.editTicket = editTicket;

async function deleteTicket(id) {
    if (!confirm('Are you sure you want to delete this support ticket?')) return;
    try {
        const res = await fetch(`${BASE_URL}/tickets/${id}`, { method: 'DELETE' });
        if (res.ok) {
            loadTickets(getSelectedLocation());
        } else {
            const err = await res.json();
            alert(`Failed to delete ticket: ${err.detail}`);
        }
    } catch (e) { console.error(e); }
}
window.deleteTicket = deleteTicket;
