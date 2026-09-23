const branchSel = document.getElementById('branch');
const rmSel = document.getElementById('rm');
const addRmToggle = document.getElementById('addRmToggle');
const addRmBox = document.getElementById('addRmBox');
const newRmName = document.getElementById('newRmName');
const saveRmBtn = document.getElementById('saveRmBtn');
const saveReportBtn = document.getElementById('saveReportBtn');
const msg = document.getElementById('msg');

const NUMERIC_FIELDS = ['dial', 'plan', 'live_int', 'reg_visit', 'reg_from_rm'];

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
  if (branchSel.value) {
    loadRMs(branchSel.value);
  } else {
    rmSel.innerHTML = '<option value="">Select branch first</option>';
    rmSel.disabled = true;
  }
});

addRmToggle.addEventListener('click', () => {
  if (!branchSel.value) { showMsg('Pick a branch first.', false); return; }
  addRmBox.classList.toggle('hidden');
});

saveRmBtn.addEventListener('click', async () => {
  const name = newRmName.value.trim();
  if (!name) return;
  saveRmBtn.disabled = true;
  try {
    await fetch('/api/rms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ branch: branchSel.value, name })
    });
    newRmName.value = '';
    addRmBox.classList.add('hidden');
    await loadRMs(branchSel.value);
    rmSel.value = name;
    showMsg('RM added.', true);
  } catch (err) {
    showMsg('Could not add RM.', false);
  } finally {
    saveRmBtn.disabled = false;
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
  } catch (err) {
    showMsg('Save failed. Try again.', false);
  } finally {
    saveReportBtn.disabled = false;
  }
});