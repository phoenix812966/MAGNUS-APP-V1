const branchSel = document.getElementById('branch');
const rmSel = document.getElementById('rm');
const saveReportBtn = document.getElementById('saveReportBtn');
const msg = document.getElementById('msg');

const NUMERIC_FIELDS = ['dial', 'plan', 'live_int', 'reg_visit', 'reg_from_rm'];

const statusBox = document.getElementById('statusBox');

async function loadStatus(branch) {
  if (!branch) { statusBox.classList.add('hidden'); return; }
  try {
    const res = await fetch(`/api/status?branch=${encodeURIComponent(branch)}`);
    if (!res.ok) throw new Error('bad response');
    const d = await res.json();
    document.getElementById('subCount').textContent = `${d.submitted}/${d.total}`;
    document.getElementById('pendCount').textContent = d.not_submitted;
    const pct = d.total ? (d.submitted / d.total) * 100 : 0;
    document.getElementById('pie').style.background =
      `conic-gradient(#0f8f7d 0 ${pct}%, #e2e4ea ${pct}% 100%)`;
    const list = document.getElementById('pendList');
    list.innerHTML = '';
    d.pending_names.forEach(n => {
      const li = document.createElement('li');
      li.textContent = n;
      list.appendChild(li);
    });
    statusBox.classList.remove('hidden');
  } catch (err) {
    statusBox.classList.add('hidden');
  }
}

function showMsg(text, ok) {
  msg.textContent = text;
  msg.className = 'msg ' + (ok ? 'ok' : 'err');
}

async function loadRMs(branch) {
  rmSel.disabled = true;
  rmSel.innerHTML = '<option value="">Loading…</option>';
  try {
    const res = await fetch(`/api/rms?branch=${encodeURIComponent(branch)}`);
    const list = await res.json();
    rmSel.innerHTML = '<option value="">Select RM</option>';
    list.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      rmSel.appendChild(opt);
    });
    rmSel.disabled = false;
  } catch (err) {
    showMsg('Could not load RM list.', false);
  }
}

branchSel.addEventListener('change', () => {
  msg.textContent = '';
  loadStatus(branchSel.value);
  if (branchSel.value) {
    loadRMs(branchSel.value);
  } else {
    rmSel.innerHTML = '<option value="">Select branch first</option>';
    rmSel.disabled = true;
  }
});

async function loadExistingReport(branch, rm) {
  try {
    const res = await fetch(`/api/reports?branch=${encodeURIComponent(branch)}&rm=${encodeURIComponent(rm)}`);
    const data = await res.json();
    NUMERIC_FIELDS.forEach(f => {
      document.getElementById(f).value = data[f] ?? 0;
    });
  } catch (err) {
    showMsg('Could not load existing data for this RM.', false);
  }
}

rmSel.addEventListener('change', () => {
  msg.textContent = '';
  if (branchSel.value && rmSel.value) {
    loadExistingReport(branchSel.value, rmSel.value);
  } else {
    NUMERIC_FIELDS.forEach(f => document.getElementById(f).value = 0);
  }
});

saveReportBtn.addEventListener('click', async () => {
  const branch = branchSel.value;
  const rm = rmSel.value;
  if (!branch) { showMsg('Select a branch.', false); return; }
  if (!rm) { showMsg('Select an RM.', false); return; }

  const payload = { branch, rm };
  NUMERIC_FIELDS.forEach(f => payload[f] = document.getElementById(f).value);

  saveReportBtn.disabled = true;
  showMsg('Saving…', true);
  try {
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('bad response');
    showMsg('Report saved ✓', true);
    NUMERIC_FIELDS.forEach(f => document.getElementById(f).value = 0);
    loadStatus(branch);
  } catch (err) {
    showMsg('Save failed. Try again.', false);
  } finally {
    saveReportBtn.disabled = false;
  }
});