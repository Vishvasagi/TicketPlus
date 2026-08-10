(() => {
  const tabs = document.querySelectorAll('.tab');
  const views = document.querySelectorAll('.view');

  const staffNotice = document.getElementById('staffNotice');
  const staffForm = document.getElementById('staffForm');
  const staffList = document.getElementById('staffList');
  const fullName = document.getElementById('fullName');
  const roleTitle = document.getElementById('roleTitle');

  const staffCount = document.getElementById('staffCount');
  const updateCount = document.getElementById('updateCount');
  const criticalCount = document.getElementById('criticalCount');
  const criticalUpdatesEl = document.getElementById('criticalUpdates');

  const updatesList = document.getElementById('updatesList');

  const filterDate = document.getElementById('filterDate');
  const filterStaff = document.getElementById('filterStaff');
  const totalReports = document.getElementById('totalReports');
  const totalTickets = document.getElementById('totalTickets');
  const totalCritical = document.getElementById('totalCritical');
  const reportList = document.getElementById('reportList');

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : ''));
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  // ---------------- Tabs ----------------

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      views.forEach(v => v.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.view).classList.add('active');

      if (tab.dataset.view === 'dashboard') loadDashboard();
      if (tab.dataset.view === 'staff') loadStaffAdmin();
      if (tab.dataset.view === 'updates') loadUpdates();
      if (tab.dataset.view === 'reports') loadReportsFilters().then(loadReports);
    });
  });

  // ---------------- Dashboard ----------------

  async function loadDashboard() {
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error();
      const data = await res.json();

      staffCount.textContent = data.staffCount;
      updateCount.textContent = data.updateCount;
      criticalCount.textContent = data.criticalCount;

      if (data.criticalUpdates.length === 0) {
        criticalUpdatesEl.innerHTML = '<div class="empty">No critical escalations right now.</div>';
        return;
      }

      criticalUpdatesEl.innerHTML = data.criticalUpdates.map(u => `
        <div class="list-row">
          <div>
            <span class="who">${escapeHtml(u.full_name)}</span><span class="role-tag">${escapeHtml(u.role_title)}</span>
            <div class="meta">Reported ${formatDate(u.report_date)} · Follow up by ${formatDate(u.follow_up_date)}</div>
            ${u.manager_remark ? `<div class="remark">${escapeHtml(u.manager_remark)}</div>` : ''}
          </div>
          <span class="badge critical">CRITICAL</span>
        </div>
      `).join('');
    } catch {
      criticalUpdatesEl.innerHTML = '<div class="empty">Could not load the dashboard. Refresh to try again.</div>';
    }
  }

  // ---------------- Staff admin ----------------

  staffForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    staffNotice.innerHTML = '';

    const submitBtn = staffForm.querySelector('.primary');
    submitBtn.disabled = true;

    try {
      const res = await fetch('/api/staff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName.value.trim(), role_title: roleTitle.value.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not add this staff member.');

      staffNotice.innerHTML = `<div class="notice success">${escapeHtml(data.full_name)} was added.</div>`;
      staffForm.reset();
      loadStaffAdmin();
    } catch (err) {
      staffNotice.innerHTML = `<div class="notice error">${escapeHtml(err.message)}</div>`;
    } finally {
      submitBtn.disabled = false;
    }
  });

  async function loadStaffAdmin() {
    try {
      const res = await fetch('/api/staff');
      if (!res.ok) throw new Error();
      const staff = await res.json();

      if (staff.length === 0) {
        staffList.innerHTML = '<div class="empty">No staff members yet. Add the first one.</div>';
        return;
      }

      staffList.innerHTML = staff.map(s => `
        <div class="staff-row" data-id="${s.id}">
          <div>
            <div class="name">${escapeHtml(s.full_name)}</div>
            <div class="role">${escapeHtml(s.role_title)}</div>
          </div>
          <button class="deactivate" type="button">Deactivate</button>
        </div>
      `).join('');

      staffList.querySelectorAll('.deactivate').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          btn.disabled = true;
          try {
            await fetch(`/api/staff/${row.dataset.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ active: false }),
            });
            row.remove();
          } catch {
            btn.disabled = false;
          }
        });
      });
    } catch {
      staffList.innerHTML = '<div class="empty">Could not load staff. Refresh to try again.</div>';
    }
  }

  // ---------------- Updates feed ----------------

  function renderReportRow(r) {
    const items = (r.items || []).map(i => `<span class="pill">${escapeHtml(i.task_name)} · ${i.pending_count}</span>`).join('');
    return `
      <div class="list-row">
        <div>
          <span class="who">${escapeHtml(r.full_name)}</span><span class="role-tag">${escapeHtml(r.role_title)}</span>
          <div class="meta">${formatDate(r.report_date)} · submitted ${formatDateTime(r.created_at)}</div>
          ${items ? `<div class="items">${items}</div>` : ''}
          ${r.is_critical && r.manager_remark ? `<div class="remark">${escapeHtml(r.manager_remark)} — follow up by ${formatDate(r.follow_up_date)}</div>` : ''}
        </div>
        ${r.is_critical ? '<span class="badge critical">CRITICAL</span>' : ''}
      </div>
    `;
  }

  async function loadUpdates() {
    try {
      const res = await fetch('/api/updates');
      if (!res.ok) throw new Error();
      const reports = await res.json();

      updatesList.innerHTML = reports.length
        ? reports.map(renderReportRow).join('')
        : '<div class="empty">No updates submitted yet.</div>';
    } catch {
      updatesList.innerHTML = '<div class="empty">Could not load updates. Refresh to try again.</div>';
    }
  }

  // ---------------- Consolidated reports ----------------

  async function loadReportsFilters() {
    try {
      const res = await fetch('/api/staff?all=1');
      if (!res.ok) throw new Error();
      const staff = await res.json();
      filterStaff.innerHTML = '<option value="">All staff</option>' +
        staff.map(s => `<option value="${s.id}">${escapeHtml(s.full_name)}</option>`).join('');
    } catch {
      // Non-fatal — filter just stays empty.
    }
  }

  async function loadReports() {
    const params = new URLSearchParams();
    if (filterDate.value) params.set('date', filterDate.value);
    if (filterStaff.value) params.set('staff_id', filterStaff.value);

    try {
      const res = await fetch(`/api/reports?${params.toString()}`);
      if (!res.ok) throw new Error();
      const data = await res.json();

      totalReports.textContent = data.totals.reports;
      totalTickets.textContent = data.totals.tickets;
      totalCritical.textContent = data.totals.critical;

      reportList.innerHTML = data.reports.length
        ? data.reports.map(renderReportRow).join('')
        : '<div class="empty">No reports match these filters.</div>';
    } catch {
      reportList.innerHTML = '<div class="empty">Could not load reports. Refresh to try again.</div>';
    }
  }

  filterDate.addEventListener('change', loadReports);
  filterStaff.addEventListener('change', loadReports);

  // Initial load
  loadDashboard();
})();
