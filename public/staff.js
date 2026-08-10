(() => {
  const notice = document.getElementById('notice');
  const staffSelect = document.getElementById('staffId');
  const reportDate = document.getElementById('reportDate');
  const tasksWrap = document.getElementById('tasks');
  const addTaskBtn = document.getElementById('addTask');
  const criticalCheckbox = document.getElementById('critical');
  const criticalFields = document.getElementById('criticalFields');
  const followDate = document.getElementById('followDate');
  const remark = document.getElementById('remark');
  const form = document.getElementById('reportForm');

  let taskSeq = 0;

  function todayISO() {
    const d = new Date();
    const tz = d.getTimezoneOffset() * 60000;
    return new Date(d - tz).toISOString().slice(0, 10);
  }

  function showNotice(message, type) {
    notice.innerHTML = `<div class="notice ${type}">${escapeHtml(message)}</div>`;
    notice.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function clearNotice() {
    notice.innerHTML = '';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function addTaskRow(name = '', count = '') {
    taskSeq += 1;
    const id = `task-${taskSeq}`;
    const row = document.createElement('div');
    row.className = 'task-row';
    row.dataset.id = id;
    row.innerHTML = `
      <input type="text" class="task-name" placeholder="e.g. Refund requests" value="${escapeHtml(name)}">
      <input type="text" inputmode="numeric" class="task-count" placeholder="Pending #" value="${escapeHtml(String(count))}">
      <button type="button" class="remove-task" aria-label="Remove task">&times;</button>
    `;
    row.querySelector('.remove-task').addEventListener('click', () => row.remove());
    tasksWrap.appendChild(row);
  }

  async function loadStaff() {
    try {
      const res = await fetch('/api/staff');
      if (!res.ok) throw new Error('Failed to load staff list.');
      const staff = await res.json();
      staffSelect.innerHTML = '<option value="" disabled selected>Select your name</option>' +
        staff.map(s => `<option value="${s.id}">${escapeHtml(s.full_name)} — ${escapeHtml(s.role_title)}</option>`).join('');
      if (staff.length === 0) {
        staffSelect.innerHTML = '<option value="" disabled selected>No staff set up yet — ask your manager</option>';
      }
    } catch (err) {
      showNotice('Could not load the staff list. Refresh to try again.', 'error');
    }
  }

  criticalCheckbox.addEventListener('change', () => {
    criticalFields.classList.toggle('open', criticalCheckbox.checked);
    followDate.required = criticalCheckbox.checked;
    remark.required = criticalCheckbox.checked;
  });

  addTaskBtn.addEventListener('click', () => addTaskRow());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearNotice();

    const tasks = Array.from(tasksWrap.querySelectorAll('.task-row')).map(row => ({
      task_name: row.querySelector('.task-name').value.trim(),
      pending_count: parseInt(row.querySelector('.task-count').value, 10) || 0,
    })).filter(t => t.task_name);

    const payload = {
      staff_id: staffSelect.value,
      report_date: reportDate.value,
      is_critical: criticalCheckbox.checked,
      manager_remark: remark.value.trim(),
      follow_up_date: followDate.value || null,
      tasks,
    };

    if (!payload.staff_id) {
      showNotice('Choose your name before sending the update.', 'error');
      return;
    }

    const submitBtn = form.querySelector('.primary');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';

    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not send the update.');

      showNotice('Update sent to your manager.', 'success');
      form.reset();
      tasksWrap.innerHTML = '';
      addTaskRow();
      criticalFields.classList.remove('open');
      reportDate.value = todayISO();
    } catch (err) {
      showNotice(err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send update';
    }
  });

  reportDate.value = todayISO();
  addTaskRow();
  loadStaff();
})();
