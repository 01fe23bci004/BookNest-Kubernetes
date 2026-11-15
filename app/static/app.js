const state = { books: [], loans: [], config: null };
const palette = ['#557c6a','#b17c61','#647998','#8b789e','#bc995e','#527c83','#a66e78','#6d8060','#63759a','#9c8265'];
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const tabToken = sessionStorage.getItem('booknestTabToken');
  if (tabToken) headers['X-BookNest-Tab'] = tabToken;
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    sessionStorage.removeItem('booknestAuthenticated');
    sessionStorage.removeItem('booknestTabToken');
    window.location.replace('/login');
    throw new Error('Please sign in again.');
  }
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
function toast(message, error = false) { const el = $('#toast'); el.textContent = message; el.className = `toast show${error ? ' error' : ''}`; clearTimeout(toast.timer); toast.timer = setTimeout(() => el.className = 'toast', 3200); }
function openModal(id) { $(`#${id}`).classList.add('open'); }
function closeModal(id) { $(`#${id}`).classList.remove('open'); }
function initials(text) { return String(text || '?').split(/\s+/).slice(0,2).map(x => x[0] || '').join('').toUpperCase(); }
function dateShort(value) { if (!value) return '—'; const d = new Date(value); return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined,{month:'short',day:'numeric'}); }

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
  $(`#view-${name}`).classList.add('active-view');
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  const labels = {dashboard:'Overview',catalogue:'Book catalogue',circulation:'Circulation',settings:'Library settings'};
  $('#breadcrumb-current').textContent = labels[name] || 'Overview';
}

async function loadStatus() {
  const status = await api('/api/status'); state.config = status;
  const cfg = status.config || {};
  const themeColors = { sage: '#557e68', ocean: '#477d96', plum: '#856b9d', sunset: '#aa765e' };
  document.documentElement.style.setProperty('--brand', themeColors[String(cfg.LIBRARY_THEME || 'sage').toLowerCase()] || themeColors.sage);
  $('#library-hours').textContent = cfg.LIBRARY_HOURS || 'Hours not configured';
  $('#announcement-text').textContent = cfg.ANNOUNCEMENT || 'Welcome to BookNest.';
  $('#loan-policy').textContent = `Up to ${cfg.MAX_BOOKS_PER_STUDENT || '—'} books per student`;
  $('#pod-indicator').textContent = `Runtime · ${status.pod || 'local'}`;
  $('#runtime-pod').textContent = status.pod || 'local';
  $('#runtime-config').textContent = status.config_file_mounted ? 'Mounted · available' : 'Environment fallback';
  $('#runtime-health').textContent = 'Healthy';
  $('#secret-state-title').textContent = status.secret_env_loaded && status.secret_file_mounted ? 'Secret mounted successfully' : 'Secret needs attention';
  $('#secret-state-copy').textContent = status.secret_values_exposed ? 'Sensitive values should not be exposed.' : 'Credentials are protected and their values are never sent to the dashboard.';
  const checks = [
    ['Secret environment variables', status.secret_env_loaded],
    ['Secret volume mounted', status.secret_file_mounted],
    ['Environment and file match', status.secret_sources_match],
    ['Credential values hidden', !status.secret_values_exposed],
  ];
  $('#secret-checks').innerHTML = checks.map(([label, ok]) => `<div class="secret-check"><span>${esc(label)}</span><span class="check-badge ${ok ? '' : 'pending'}">${ok ? '✓ Verified' : 'Check'}</span></div>`).join('');
  const configRows = [
    ['Library name','LIBRARY_NAME'],['Opening hours','LIBRARY_HOURS'],['Maximum books','MAX_BOOKS_PER_STUDENT'],['Late return fee','LATE_RETURN_FEE'],['Announcement','ANNOUNCEMENT'],['Theme','LIBRARY_THEME']
  ];
  $('#config-list').innerHTML = configRows.map(([label,key]) => `<div class="config-row"><span>${esc(label)}</span><code>${esc(cfg[key] || 'Not configured')}</code></div>`).join('');
  $('#service-status').textContent = 'Service online';
}
async function loadStats() {
  const stats = await api('/api/stats');
  $('#stat-titles').textContent = stats.book_titles;
  $('#stat-available').textContent = stats.available_copies;
  $('#stat-issued').textContent = stats.active_loans;
  $('#stat-readers').textContent = stats.active_students;
  $('#updated-label').textContent = `Updated ${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
}
async function loadBooks(search = '') {
  state.books = await api(`/api/books?search=${encodeURIComponent(search)}`);
  $('#book-count').textContent = `${state.books.length} titles found`;
  renderBooks(); renderFeatured(); fillBookSelect();
}
function renderFeatured() {
  const picks = state.books.slice(0,3);
  $('#featured-books').innerHTML = picks.length ? picks.map((book,i) => `<div class="mini-book"><div class="book-cover" style="background:${palette[(book.id-1)%palette.length]}">${esc(initials(book.title).slice(0,1))}</div><div class="mini-book-copy"><strong>${esc(book.title)}</strong><small>${esc(book.author)}</small></div></div>`).join('') : '<div class="empty-small">Add books to start your collection.</div>';
}
function renderBooks() {
  $('#book-grid').innerHTML = state.books.length ? state.books.map(book => {
    const color = palette[(book.id-1)%palette.length];
    return `<article class="book-card"><div class="book-art" style="background:linear-gradient(145deg,${color},${color}dd)"><span>${esc(initials(book.title).slice(0,1))}</span></div><div class="book-category">${esc(book.category)}</div><h3>${esc(book.title)}</h3><p class="author">by ${esc(book.author)}</p><div class="book-card-foot"><span class="availability ${book.available_copies ? '' : 'out'}">${book.available_copies ? `${book.available_copies} available` : 'Currently issued'}</span><span class="copies">${book.total_copies} total</span></div></article>`;
  }).join('') : '<div class="empty-small">No books matched your search.</div>';
}
function fillBookSelect() {
  const select = $('#issue-book'); const previous = select.value;
  select.innerHTML = '<option value="">Select from catalogue</option>' + state.books.filter(b => b.available_copies > 0).map(b => `<option value="${b.id}">${esc(b.title)} · ${b.available_copies} available</option>`).join('');
  if ([...select.options].some(o => o.value === previous)) select.value = previous;
}
async function loadLoans() {
  state.loans = await api('/api/loans');
  const active = state.loans.filter(loan => !loan.returned_on);
  $('#loan-count').textContent = `${active.length} active`;
  $('#loan-table').innerHTML = state.loans.length ? state.loans.map(loan => `<tr><td><div class="reader-cell"><span class="reader-initial">${esc(initials(loan.student_name))}</span><span><strong>${esc(loan.student_name)}</strong><br><small>${esc(loan.student_id)}</small></span></div></td><td>${esc(loan.book_title)}</td><td>${dateShort(loan.issued_on)}</td><td>${loan.returned_on ? '<span class="returned-label">Returned</span>' : `<button class="return-button" data-return="${loan.id}">Mark returned</button>`}</td></tr>`).join('') : '<tr><td colspan="4" class="table-empty">No borrowing records yet. Issue your first book.</td></tr>';
  const recent = state.loans.slice(0,4);
  $('#recent-activity').innerHTML = recent.length ? recent.map(loan => `<div class="activity-row"><div class="activity-avatar">${esc(initials(loan.student_name))}</div><div class="activity-copy"><strong>${esc(loan.student_name)} ${loan.returned_on ? 'returned' : 'borrowed'}</strong><small>${esc(loan.book_title)} · ${dateShort(loan.returned_on || loan.issued_on)}</small></div><span class="activity-status">${loan.returned_on ? 'Returned' : 'Issued'}</span></div>`).join('') : '<div class="empty-small">No activity yet. Your first book is waiting.</div>';
}
async function refreshAll() { try { await Promise.all([loadStatus(),loadStats(),loadBooks($('#book-search')?.value || ''),loadLoans()]); } catch (e) { $('#service-status').textContent = 'Service issue'; toast(e.message, true); } }

async function handleIssue(event) {
  event.preventDefault();
  try {
    const result = await api('/api/loans', {method:'POST',body:JSON.stringify({book_id:Number($('#issue-book').value),student_name:$('#student-name').value,student_id:$('#student-id').value})});
    $('#issue-form').reset(); toast(result.message || 'Book issued successfully.'); await Promise.all([loadStats(),loadBooks($('#book-search').value),loadLoans()]);
  } catch (e) { toast(e.message,true); }
}
async function handleReturn(loanId) {
  try { const result = await api('/api/returns',{method:'POST',body:JSON.stringify({loan_id:Number(loanId)})}); toast(result.message); await Promise.all([loadStats(),loadBooks($('#book-search').value),loadLoans()]); }
  catch(e) { toast(e.message,true); }
}
async function handleAddBook(event) {
  event.preventDefault();
  const payload = {title:$('#new-title').value,author:$('#new-author').value,category:$('#new-category').value,isbn:$('#new-isbn').value,copies:Number($('#new-copies').value)};
  try { await api('/api/books',{method:'POST',body:JSON.stringify(payload)}); closeModal('add-modal'); $('#add-book-form').reset(); $('#new-copies').value = 1; toast('New title added to the collection.'); await Promise.all([loadBooks($('#book-search').value),loadStats()]); }
  catch(e) { toast(e.message,true); }
}

document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click',() => showView(button.dataset.view)));
document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click',() => showView(button.dataset.go)));
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click',() => closeModal(button.dataset.close)));
document.querySelectorAll('.modal-backdrop').forEach(backdrop => backdrop.addEventListener('click',e => { if(e.target === backdrop) backdrop.classList.remove('open'); }));
$('#add-book-btn').addEventListener('click',() => openModal('add-modal'));
$('#logout-btn').addEventListener('click', async () => {
  try { await fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' }); }
  finally { sessionStorage.removeItem('booknestAuthenticated'); sessionStorage.removeItem('booknestTabToken'); window.location.replace('/login'); }
});
$('#refresh-btn').addEventListener('click',refreshAll); $('#settings-refresh').addEventListener('click',async()=>{try{await loadStatus();toast('Configuration refreshed from Kubernetes.');}catch(e){toast(e.message,true);}});
$('#issue-form').addEventListener('submit',handleIssue); $('#add-book-form').addEventListener('submit',handleAddBook);
$('#loan-table').addEventListener('click',e=>{const button=e.target.closest('[data-return]');if(button)handleReturn(button.dataset.return);});
let searchTimer; $('#book-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadBooks($('#book-search').value).catch(e=>toast(e.message,true)),180);});
$('#today-label').textContent = new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'}).toUpperCase();
refreshAll();

// Re-check the tab-only marker when a browser restores a page from its back-forward cache.
window.addEventListener('pageshow', () => {
  if (sessionStorage.getItem('booknestAuthenticated') !== 'yes') window.location.replace('/login');
});
