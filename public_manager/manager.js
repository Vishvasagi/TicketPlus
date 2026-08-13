(() => {
  const loginScreen = document.getElementById('loginScreen');
  const appContainer = document.getElementById('appContainer');
  const loginForm = document.getElementById('loginForm');
  const loginNotice = document.getElementById('loginNotice');
  const loginUsername = document.getElementById('loginUsername');
  const loginPassword = document.getElementById('loginPassword');
  const logoutBtn = document.getElementById('logoutBtn');
  const whoami = document.getElementById('whoami');

  const tabs = document.querySelectorAll('.tab');
  const views = document.querySelectorAll('.view');

  // Staff
  const staffNotice = document.getElementById('staffNotice');
  const staffForm = document.getElementById('staffForm');
  const staffList = document.getElementById('staffList');
  const fullName = document.getElementById('fullName');
  const roleTitle = document.getElementById('roleTitle');
  const staffDepartment = document.getElementById('staffDepartment');
  const staffUsername = document.getElementById('staffUsername');
  const staffPassword = document.getElementById('staffPassword');
  const staffIsAdmin = document.getElementById('staffIsAdmin');

  // Manager accounts
  const managerNotice = document.getElementById('managerNotice');
  const managerForm = document.getElementById('managerForm');
  const managerFullName = document.getElementById('managerFullName');
  const managerUsername = document.getElementById('managerUsername');
  const managerPassword = document.getElementById('managerPassword');
  const managerList = document.getElementById('managerList');

  // Departments
  const deptNotice = document.getElementById('deptNotice');
  const deptForm = document.getElementById('deptForm');
  const deptName = document.getElementById('deptName');
  const deptList = document.getElementById('deptList');

  // Statuses
  const statusNotice = document.getElementById('statusNotice');
  const statusForm = document.getElementById('statusForm');
  const statusName = document.getElementById('statusName');
  const statusList = document.getElementById('statusList');

  // Dashboard
  const staffCount = document.getElementById('staffCount');
  const updateCount = document.getElementById('updateCount');
  const criticalCount = document.getElementById('criticalCount');
  const criticalUpdatesEl = document.getElementById('criticalUpdates');

  // Updates
  const updatesList = document.getElementById('updatesList');

  // Reports
  const filterDate = document.getElementById('filterDate');
  const filterStaff = document.getElementById('filterStaff');
  const totalReports = document.getElementById('totalReports');
  const totalTickets = document.getElementById('totalTickets');
  const totalCritical = document.getElementById('totalCritical');
  const reportList = document.getElementById('reportList');

  let departmentsCache = [];

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

  function showNotice(el, message, type) {
    el.innerHTML = `<div class="notice ${type}">${escapeHtml(message)}</div>`;
  }

  // ---------------- Auth ----------------

  async function checkSession() {
    try {
      const res = await fetch('/api/auth/me');
      if (!res.ok) throw new Error();
      const me = await res.json();
      showApp(me);
    } catch {
      showLogin();
    }
  }

  function showApp(me) {
    loginScreen.style.display = 'none';
    appContainer.style.display = '';
    whoami.textContent = me.full_name;
    loadDashboard();
  }

  function showLogin() {
    appContainer.style.display = 'none';
    loginScreen.style.display = '';
  }

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginNotice.innerHTML = '';
    const btn = loginForm.querySelector('.primary');
    btn.disabled = true;
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername.value.trim(), password: loginPassword.value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not sign in.');
      loginPassword.value = '';
      showApp(data);
    } catch (err) {
      showNotice(loginNotice, err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  logoutBtn.addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    showLogin();
  });

  // ---------------- Tabs ----------------

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      views.forEach(v => v.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.view).classList.add('active');

      if (tab.dataset.view === 'dashboard') loadDashboard();
      if (tab.dataset.view === 'staff') { loadDepartmentsInto(staffDepartment, false); loadStaffAdmin(); }
      if (tab.dataset.view === 'managers') loadManagers();
      if (tab.dataset.view === 'departments') loadDepartments();
      if (tab.dataset.view === 'statuses') loadStatuses();
      if (tab.dataset.view === 'updates') loadUpdates();
      if (tab.dataset.view === 'reports') loadReportsFilters().then(loadReports);
    });
  });

  // ---------------- Dashboard ----------------

  async function loadDashboard() {
    try {
      const res = await fetch('/api/dashboard');
      if (res.status === 401) return showLogin();
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
            <span class="who">${escapeHtml(u.full_name)}</span><span class="role-tag">${escapeHtml(u.role_title)}${u.department_name ? ' · ' + escapeHtml(u.department_name) : ''}</span>
            <div class="meta">${escapeHtml(u.status_name)} · ${u.pending_count} pending · reported ${formatDate(u.report_date)} · follow up by ${formatDate(u.follow_up_date)}</div>
            ${u.manager_remark ? `<div class="remark">${escapeHtml(u.manager_remark)}</div>` : ''}
          </div>
          <span class="badge critical">CRITICAL</span>
        </div>
      `).join('');
    } catch {
      criticalUpdatesEl.innerHTML = '<div class="empty">Could not load the dashboard. Refresh to try again.</div>';
    }
  }

  // ---------------- Departments ----------------

  async function loadDepartmentsInto(selectEl, includeBlank) {
    try {
      const res = await fetch('/api/departments');
      if (!res.ok) throw new Error();
      departmentsCache = await res.json();
      selectEl.innerHTML = (includeBlank ? '<option value="">All departments</option>' : '<option value="">No department</option>') +
        departmentsCache.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
    } catch {
      selectEl.innerHTML = '<option value="">Could not load departments</option>';
    }
  }

  deptForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    deptNotice.innerHTML = '';
    const btn = deptForm.querySelector('.primary');
    btn.disabled = true;
    try {
      const res = await fetch('/api/departments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: deptName.value.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not add this department.');
      showNotice(deptNotice, `${data.name} was added.`, 'success');
      deptForm.reset();
      loadDepartments();
    } catch (err) {
      showNotice(deptNotice, err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  async function loadDepartments() {
    try {
      const res = await fetch('/api/departments?all=1');
      if (!res.ok) throw new Error();
      const depts = await res.json();

      deptList.innerHTML = depts.length ? depts.map(d => `
        <div class="staff-row" data-id="${d.id}">
          <div><div class="name">${escapeHtml(d.name)}</div>${!d.active ? '<div class="role">Inactive</div>' : ''}</div>
          <div style="display:flex;gap:8px">
            <button class="deactivate toggle-active" type="button">${d.active ? 'Deactivate' : 'Activate'}</button>
            <button class="deactivate delete-dept" type="button">Delete</button>
          </div>
        </div>
      `).join('') : '<div class="empty">No departments yet. Add the first one.</div>';

      deptList.querySelectorAll('.toggle-active').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          const isActive = btn.textContent.trim() === 'Deactivate';
          await fetch(`/api/departments/${row.dataset.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: !isActive }),
          });
          loadDepartments();
        });
      });

      deptList.querySelectorAll('.delete-dept').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Delete this department? Staff assigned to it will show no department.')) return;
          const res = await fetch(`/api/departments/${row.dataset.id}`, { method: 'DELETE' });
          const data = await res.json();
          if (!res.ok) { showNotice(deptNotice, data.error || 'Could not delete.', 'error'); return; }
          loadDepartments();
        });
      });
    } catch {
      deptList.innerHTML = '<div class="empty">Could not load departments. Refresh to try again.</div>';
    }
  }

  // ---------------- Ticket statuses ----------------

  statusForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    statusNotice.innerHTML = '';
    const btn = statusForm.querySelector('.primary');
    btn.disabled = true;
    try {
      const res = await fetch('/api/statuses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: statusName.value.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not add this status.');
      showNotice(statusNotice, `${data.name} was added.`, 'success');
      statusForm.reset();
      loadStatuses();
    } catch (err) {
      showNotice(statusNotice, err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  async function loadStatuses() {
    try {
      const res = await fetch('/api/statuses?all=1');
      if (!res.ok) throw new Error();
      const statuses = await res.json();

      statusList.innerHTML = statuses.length ? statuses.map(s => `
        <div class="staff-row" data-id="${s.id}">
          <div><div class="name">${escapeHtml(s.name)}</div>${!s.active ? '<div class="role">Inactive</div>' : ''}</div>
          <div style="display:flex;gap:8px">
            <button class="deactivate toggle-active" type="button">${s.active ? 'Deactivate' : 'Activate'}</button>
            <button class="deactivate delete-status" type="button">Delete</button>
          </div>
        </div>
      `).join('') : '<div class="empty">No ticket statuses yet. Add the first one.</div>';

      statusList.querySelectorAll('.toggle-active').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          const isActive = btn.textContent.trim() === 'Deactivate';
          await fetch(`/api/statuses/${row.dataset.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: !isActive }),
          });
          loadStatuses();
        });
      });

      statusList.querySelectorAll('.delete-status').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Delete this status? Past reports that used it will keep it, but staff can no longer pick it.')) return;
          const res = await fetch(`/api/statuses/${row.dataset.id}`, { method: 'DELETE' });
          const data = await res.json();
          if (!res.ok) { showNotice(statusNotice, data.error || 'Could not delete.', 'error'); return; }
          loadStatuses();
        });
      });
    } catch {
      statusList.innerHTML = '<div class="empty">Could not load statuses. Refresh to try again.</div>';
    }
  }

  // ---------------- Staff admin ----------------

  staffForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    staffNotice.innerHTML = '';
    const btn = staffForm.querySelector('.primary');
    btn.disabled = true;

    try {
      const res = await fetch('/api/staff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName.value.trim(),
          role_title: roleTitle.value.trim(),
          department_id: staffDepartment.value || null,
          username: staffUsername.value.trim(),
          password: staffPassword.value,
          is_admin: staffIsAdmin.checked,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not add this staff member.');

      let msg = `${data.full_name} was added.`;
      if (data.temp_password) msg += ` Auto-generated password: ${data.temp_password} — share this with them securely.`;
      showNotice(staffNotice, msg, 'success');
      staffForm.reset();
      loadStaffAdmin();
    } catch (err) {
      showNotice(staffNotice, err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  function departmentOptionsHtml(selectedId) {
    return '<option value="">No department</option>' +
      departmentsCache.map(d => `<option value="${d.id}" ${String(d.id) === String(selectedId) ? 'selected' : ''}>${escapeHtml(d.name)}</option>`).join('');
  }

  function staffRowHtml(s) {
    return `
        <div class="staff-row" data-id="${s.id}" data-dept="${s.department_id || ''}">
          <div>
            <div class="name">${escapeHtml(s.full_name)} ${!s.active ? '<span class="role">(inactive)</span>' : ''}</div>
            <div class="role">${escapeHtml(s.role_title)}${s.department_name ? ' · ' + escapeHtml(s.department_name) : ''} · @${escapeHtml(s.username)}${s.is_admin ? ' · <b>Admin</b>' : ''}</div>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
            <button class="deactivate edit-staff" type="button">Edit</button>
            <button class="deactivate reset-pw" type="button">Reset password</button>
            <button class="deactivate toggle-active" type="button">${s.active ? 'Deactivate' : 'Activate'}</button>
            <button class="deactivate delete-staff" type="button">Delete</button>
          </div>
        </div>
      `;
  }

  async function loadStaffAdmin() {
    try {
      const res = await fetch('/api/staff?all=1');
      if (!res.ok) throw new Error();
      const staff = await res.json();

      if (staff.length === 0) {
        staffList.innerHTML = '<div class="empty">No staff members yet. Add the first one.</div>';
        return;
      }

      const adminStaff = staff.filter(s => s.is_admin);
      const regularStaff = staff.filter(s => !s.is_admin);

      const groupLabel = (text, count) => `
        <div class="help" style="margin:${text === 'Manager page access' ? '0' : '18px'} 0 8px;font-weight:600;text-transform:uppercase;letter-spacing:.04em">
          ${text} (${count})
        </div>
      `;

      staffList.innerHTML =
        groupLabel('Manager page access', adminStaff.length) +
        (adminStaff.length ? adminStaff.map(staffRowHtml).join('') : '<div class="empty">No staff with Manager page access.</div>') +
        groupLabel('Staff portal only', regularStaff.length) +
        (regularStaff.length ? regularStaff.map(staffRowHtml).join('') : '<div class="empty">No staff-only members.</div>');

      staffList.querySelectorAll('.toggle-active').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          const isActive = btn.textContent.trim() === 'Deactivate';
          await fetch(`/api/staff/${row.dataset.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: !isActive }),
          });
          loadStaffAdmin();
        });
      });

      staffList.querySelectorAll('.delete-staff').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Delete this staff member permanently? Their past reports will be deleted too. Consider Deactivate instead if you want to keep history.')) return;
          const res = await fetch(`/api/staff/${row.dataset.id}`, { method: 'DELETE' });
          const data = await res.json();
          if (!res.ok) { showNotice(staffNotice, data.error || 'Could not delete.', 'error'); return; }
          loadStaffAdmin();
        });
      });

      staffList.querySelectorAll('.reset-pw').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Reset this staff member\'s password? A new random password will be generated.')) return;
          const res = await fetch(`/api/staff/${row.dataset.id}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
          });
          const data = await res.json();
          if (!res.ok) { showNotice(staffNotice, data.error || 'Could not reset password.', 'error'); return; }
          showNotice(staffNotice, `New password: ${data.new_password} — share this with them securely.`, 'success');
        });
      });

      staffList.querySelectorAll('.edit-staff').forEach(btn => {
        btn.addEventListener('click', () => openEditRow(btn.closest('.staff-row'), staff.find(s => String(s.id) === btn.closest('.staff-row').dataset.id)));
      });
    } catch {
      staffList.innerHTML = '<div class="empty">Could not load staff. Refresh to try again.</div>';
    }
  }

  function openEditRow(row, s) {
    row.innerHTML = `
      <div style="width:100%">
        <div class="two">
          <div class="field"><label>Full name</label><input class="edit-name" value="${escapeHtml(s.full_name)}"></div>
          <div class="field"><label>Team / role</label><input class="edit-role" value="${escapeHtml(s.role_title)}"></div>
        </div>
        <div class="field"><label>Department</label><select class="edit-dept">${departmentOptionsHtml(s.department_id)}</select></div>
        <div class="field">
          <label style="display:flex;align-items:center;gap:8px;font-weight:normal">
            <input type="checkbox" class="edit-is-admin" ${s.is_admin ? 'checked' : ''} style="width:auto">
            Admin staff — can also sign in to the Manager page with these credentials
          </label>
        </div>
        <div class="actions">
          <button type="button" class="outline cancel-edit">Cancel</button>
          <button type="button" class="primary save-edit">Save</button>
        </div>
      </div>
    `;
    row.querySelector('.cancel-edit').addEventListener('click', () => loadStaffAdmin());
    row.querySelector('.save-edit').addEventListener('click', async () => {
      const body = {
        full_name: row.querySelector('.edit-name').value.trim(),
        role_title: row.querySelector('.edit-role').value.trim(),
        department_id: row.querySelector('.edit-dept').value || null,
        is_admin: row.querySelector('.edit-is-admin').checked,
      };
      const res = await fetch(`/api/staff/${row.dataset.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showNotice(staffNotice, data.error || 'Could not save changes.', 'error'); return; }
      showNotice(staffNotice, `${data.full_name} was updated.`, 'success');
      loadStaffAdmin();
    });
  }

  // ---------------- Manager accounts ----------------

  managerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    managerNotice.innerHTML = '';
    const btn = managerForm.querySelector('.primary');
    btn.disabled = true;
    try {
      const res = await fetch('/api/managers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: managerFullName.value.trim(),
          username: managerUsername.value.trim(),
          password: managerPassword.value,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not add this manager.');

      let msg = `${data.full_name} was added.`;
      if (data.temp_password) msg += ` Auto-generated password: ${data.temp_password} — share this with them securely.`;
      showNotice(managerNotice, msg, 'success');
      managerForm.reset();
      loadManagers();
    } catch (err) {
      showNotice(managerNotice, err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  function managerRowHtml(m) {
    return `
        <div class="staff-row" data-id="${m.id}">
          <div>
            <div class="name">${escapeHtml(m.full_name)}</div>
            <div class="role">@${escapeHtml(m.username)}${m.linked_staff_name ? ` · Linked to staff: ${escapeHtml(m.linked_staff_name)}` : ''}</div>
          </div>
          ${m.staff_id ? '<div class="help" style="margin:0">Manage from Staff tab</div>' : `
          <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
            <button class="deactivate edit-manager" type="button">Edit</button>
            <button class="deactivate reset-manager-pw" type="button">Reset password</button>
            <button class="deactivate delete-manager" type="button">Delete</button>
          </div>
          `}
        </div>
      `;
  }

  async function loadManagers() {
    try {
      const res = await fetch('/api/managers');
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.error || `Request failed (${res.status})`);
      }
      const managers = await res.json();

      if (managers.length === 0) {
        managerList.innerHTML = '<div class="empty">No manager accounts yet. Add the first one.</div>';
        return;
      }

      const fromStaff = managers.filter(m => m.staff_id);
      const standalone = managers.filter(m => !m.staff_id);

      const groupLabel = (text, count, first) => `
        <div class="help" style="margin:${first ? '0' : '18px'} 0 8px;font-weight:600;text-transform:uppercase;letter-spacing:.04em">
          ${text} (${count})
        </div>
      `;

      managerList.innerHTML =
        groupLabel('Admin staff (from Staff tab)', fromStaff.length, true) +
        (fromStaff.length ? fromStaff.map(managerRowHtml).join('') : '<div class="empty">No staff currently have Manager page access.</div>') +
        groupLabel('Standalone manager accounts', standalone.length, false) +
        (standalone.length ? standalone.map(managerRowHtml).join('') : '<div class="empty">No standalone manager accounts yet.</div>');

      managerList.querySelectorAll('.delete-manager').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Delete this manager account? They will no longer be able to sign in to the Manager page.')) return;
          const res = await fetch(`/api/managers/${row.dataset.id}`, { method: 'DELETE' });
          const data = await res.json();
          if (!res.ok) { showNotice(managerNotice, data.error || 'Could not delete.', 'error'); return; }
          loadManagers();
        });
      });

      managerList.querySelectorAll('.reset-manager-pw').forEach(btn => {
        btn.addEventListener('click', async () => {
          const row = btn.closest('.staff-row');
          if (!confirm('Reset this manager\'s password? A new random password will be generated.')) return;
          const res = await fetch(`/api/managers/${row.dataset.id}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
          });
          const data = await res.json();
          if (!res.ok) { showNotice(managerNotice, data.error || 'Could not reset password.', 'error'); return; }
          showNotice(managerNotice, `New password: ${data.new_password} — share this with them securely.`, 'success');
        });
      });

      managerList.querySelectorAll('.edit-manager').forEach(btn => {
        btn.addEventListener('click', () => openEditManagerRow(btn.closest('.staff-row'), managers.find(m => String(m.id) === btn.closest('.staff-row').dataset.id)));
      });
    } catch (err) {
      console.error('loadManagers failed:', err);
      managerList.innerHTML = `<div class="empty">Could not load manager accounts: ${escapeHtml(err.message || 'unknown error')}. Refresh to try again.</div>`;
    }
  }

  function openEditManagerRow(row, m) {
    row.innerHTML = `
      <div style="width:100%">
        <div class="two">
          <div class="field"><label>Full name</label><input class="edit-mgr-name" value="${escapeHtml(m.full_name)}"></div>
          <div class="field"><label>Username</label><input class="edit-mgr-username" value="${escapeHtml(m.username)}"></div>
        </div>
        <div class="actions">
          <button type="button" class="outline cancel-mgr-edit">Cancel</button>
          <button type="button" class="primary save-mgr-edit">Save</button>
        </div>
      </div>
    `;
    row.querySelector('.cancel-mgr-edit').addEventListener('click', () => loadManagers());
    row.querySelector('.save-mgr-edit').addEventListener('click', async () => {
      const body = {
        full_name: row.querySelector('.edit-mgr-name').value.trim(),
        username: row.querySelector('.edit-mgr-username').value.trim(),
      };
      const res = await fetch(`/api/managers/${row.dataset.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showNotice(managerNotice, data.error || 'Could not save changes.', 'error'); return; }
      showNotice(managerNotice, `${data.full_name} was updated.`, 'success');
      loadManagers();
    });
  }

  // ---------------- Updates feed ----------------

  function renderReportRow(r) {
    const items = (r.items || []).map(i => {
      const critical = i.is_critical ? ' badge-inline' : '';
      return `<span class="pill${critical}">${escapeHtml(i.status_name)} · ${i.pending_count}${i.is_critical ? ' · CRITICAL' : ''}</span>`;
    }).join('');
    const criticalRemarks = (r.items || []).filter(i => i.is_critical && i.manager_remark);
    const anyCritical = (r.items || []).some(i => i.is_critical);

    return `
      <div class="list-row">
        <div>
          <span class="who">${escapeHtml(r.full_name)}</span><span class="role-tag">${escapeHtml(r.role_title)}${r.department_name ? ' · ' + escapeHtml(r.department_name) : ''}</span>
          <div class="meta">${formatDate(r.report_date)} · submitted ${formatDateTime(r.created_at)}</div>
          ${items ? `<div class="items">${items}</div>` : ''}
          ${criticalRemarks.map(i => `<div class="remark">${escapeHtml(i.status_name)}: ${escapeHtml(i.manager_remark)} — follow up by ${formatDate(i.follow_up_date)}</div>`).join('')}
        </div>
        ${anyCritical ? '<span class="badge critical">CRITICAL</span>' : ''}
      </div>
    `;
  }

  async function loadUpdates() {
    try {
      const res = await fetch('/api/updates');
      if (!res.ok) throw new Error();
      const reports = await res.json();
      updatesList.innerHTML = reports.length ? reports.map(renderReportRow).join('') : '<div class="empty">No updates submitted yet.</div>';
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
    } catch { /* non-fatal */ }
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

      reportList.innerHTML = data.reports.length ? data.reports.map(renderReportRow).join('') : '<div class="empty">No reports match these filters.</div>';
    } catch {
      reportList.innerHTML = '<div class="empty">Could not load reports. Refresh to try again.</div>';
    }
  }

  filterDate.addEventListener('change', loadReports);
  filterStaff.addEventListener('change', loadReports);

  checkSession();
})();
