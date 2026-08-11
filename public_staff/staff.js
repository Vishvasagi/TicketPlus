(() => {
  const loginScreen = document.getElementById('loginScreen');
  const appContainer = document.getElementById('appContainer');
  const loginForm = document.getElementById('loginForm');
  const loginNotice = document.getElementById('loginNotice');
  const loginUsername = document.getElementById('loginUsername');
  const loginPassword = document.getElementById('loginPassword');
  const logoutBtn = document.getElementById('logoutBtn');
  const whoami = document.getElementById('whoami');

  const notice = document.getElementById('notice');
  const reportDate = document.getElementById('reportDate');
  const statusesWrap = document.getElementById('statuses');
  const addStatusBtn = document.getElementById('addStatus');
  const form = document.getElementById('reportForm');

  let statusOptions = [];
  let rowSeq = 0;

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  function todayISO() {
    const d = new Date();
    const tz = d.getTimezoneOffset() * 60000;
    return new Date(d - tz).toISOString().slice(0, 10);
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
    whoami.textContent = `${me.full_name} · ${me.role_title || ''}`;
    reportDate.value = todayISO();
    statusesWrap.innerHTML = '';
    loadStatuses().then(() => addStatusRow());
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

  // ---------------- Statuses / report rows ----------------

  async function loadStatuses() {
    try {
      const res = await fetch('/api/statuses');
      if (!res.ok) throw new Error();
      statusOptions = await res.json();
    } catch {
      statusOptions = [];
      showNotice(notice, 'Could not load ticket statuses. Refresh to try again.', 'error');
    }
  }

  function statusOptionsHtml(selected) {
    if (statusOptions.length === 0) {
      return '<option value="" disabled selected>No statuses set up — ask your manager</option>';
    }
    return '<option value="" disabled' + (selected ? '' : ' selected') + '>Select a status</option>' +
      statusOptions.map(s => `<option value="${s.id}" ${String(s.id) === String(selected) ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('');
  }

  function addStatusRow() {
    rowSeq += 1;
    const id = `row-${rowSeq}`;
    const row = document.createElement('div');
    row.className = 'card';
    row.dataset.id = id;
    row.style.padding = '14px';
    row.innerHTML = `
      <div class="task-row" style="grid-template-columns:1fr 110px 32px;margin-bottom:8px">
        <select class="status-select">${statusOptionsHtml()}</select>
        <input type="text" inputmode="numeric" class="status-count" placeholder="Pending #">
        <button type="button" class="remove-row" aria-label="Remove status">&times;</button>
      </div>
      <label class="toggle" style="margin:6px 0">
        <input type="checkbox" class="status-critical"> Mark this status as critical — needs manager follow-up
      </label>
      <div class="conditional critical-fields">
        <div class="two">
          <div class="field"><label>Follow-up target date</label><input type="date" class="status-followup"></div>
          <div class="field"><label>Remark for manager</label><textarea class="status-remark" placeholder="Explain the blocker or escalation."></textarea></div>
        </div>
      </div>
    `;

    row.querySelector('.remove-row').addEventListener('click', () => row.remove());

    const criticalCheckbox = row.querySelector('.status-critical');
    const criticalFields = row.querySelector('.critical-fields');
    const followup = row.querySelector('.status-followup');
    const remark = row.querySelector('.status-remark');

    criticalCheckbox.addEventListener('change', () => {
      criticalFields.classList.toggle('open', criticalCheckbox.checked);
      followup.required = criticalCheckbox.checked;
      remark.required = criticalCheckbox.checked;
    });

    statusesWrap.appendChild(row);
  }

  addStatusBtn.addEventListener('click', () => addStatusRow());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    notice.innerHTML = '';

    const items = Array.from(statusesWrap.querySelectorAll('.card')).map(row => ({
      status_id: row.querySelector('.status-select').value,
      pending_count: parseInt(row.querySelector('.status-count').value, 10) || 0,
      is_critical: row.querySelector('.status-critical').checked,
      manager_remark: row.querySelector('.status-remark').value.trim(),
      follow_up_date: row.querySelector('.status-followup').value || null,
    })).filter(i => i.status_id);

    if (items.length === 0) {
      showNotice(notice, 'Add at least one status before sending.', 'error');
      return;
    }

    const missingCritical = items.find(i => i.is_critical && (!i.manager_remark || !i.follow_up_date));
    if (missingCritical) {
      showNotice(notice, 'Each status marked critical needs a remark and a follow-up date.', 'error');
      return;
    }

    const submitBtn = form.querySelector('.primary');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';

    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_date: reportDate.value, items }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not send the update.');

      showNotice(notice, 'Update sent to your manager.', 'success');
      statusesWrap.innerHTML = '';
      addStatusRow();
      reportDate.value = todayISO();
    } catch (err) {
      showNotice(notice, err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send update';
    }
  });

  checkSession();
})();
