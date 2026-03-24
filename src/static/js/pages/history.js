window.Pages = window.Pages || {};

let _page = 1;
const _perPage = 20;
let _sort = { col: 'created_at', dir: 'desc' };
let _filters = { status: '', model: '', minQuality: 0, maxQuality: 100 };

function sortableValue(job, col) {
  if (col === 'title') return (DB.dbGet('books', job.book_id)?.title || '').toLowerCase();
  if (col === 'quality_score') return Number(job.quality_score || 0);
  if (col === 'cost_usd') return Number(job.cost_usd || 0);
  if (col === 'created_at') return new Date(job.created_at || 0).getTime();
  return String(job[col] || '').toLowerCase();
}

function statusClass(status) {
  if (status === 'completed') return 'tag-success';
  if (status === 'failed' || status === 'cancelled') return 'tag-failed';
  if (status === 'queued') return 'tag-queued';
  return 'tag-pending';
}

window.Pages.history = {
  async render() {
    const models = [...new Set(DB.dbGetAll('jobs').map((j) => j.model).filter(Boolean))];
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="card">
        <div class="flex justify-between mb-8">
          <h3 class="card-title">Job History</h3>
          <button class="btn btn-secondary" id="histExportBtn">⬇ Export CSV</button>
        </div>
        <div class="filters-bar mb-8">
          <select class="form-select" id="histStatusFilter" style="max-width:170px">
            <option value="">All Status</option>
            <option value="queued">queued</option>
            <option value="generating">generating</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
          <select class="form-select" id="histModelFilter" style="max-width:280px">
            <option value="">All Models</option>
            ${models.map((m) => `<option value="${m}">${m}</option>`).join('')}
          </select>
          <input class="form-input" type="number" id="histMinQuality" placeholder="Min %" style="width:70px" />
          <span>–</span>
          <input class="form-input" type="number" id="histMaxQuality" placeholder="Max %" style="width:70px" />
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th data-col="title">Book <span class="sort-icon">↕</span></th>
                <th data-col="model">Model <span class="sort-icon">↕</span></th>
                <th data-col="variant">Variant</th>
                <th data-col="status">Status</th>
                <th data-col="quality_score">Quality <span class="sort-icon">↕</span></th>
                <th data-col="cost_usd">Cost <span class="sort-icon">↕</span></th>
                <th data-col="created_at">Date <span class="sort-icon">↕</span></th>
              </tr>
            </thead>
            <tbody id="histBody"></tbody>
          </table>
        </div>
        <div class="pagination" id="histPagination"></div>
      </div>
    `;

    document.querySelectorAll('#histStatusFilter, #histModelFilter, #histMinQuality, #histMaxQuality').forEach((el) => {
      el.addEventListener('change', () => {
        _filters = {
          status: document.getElementById('histStatusFilter').value,
          model: document.getElementById('histModelFilter').value,
          minQuality: Number(document.getElementById('histMinQuality').value || 0),
          maxQuality: Number(document.getElementById('histMaxQuality').value || 100),
        };
        _page = 1;
        this.renderTable();
      });
    });

    document.querySelectorAll('th[data-col]').forEach((th) => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (_sort.col === col) _sort.dir = _sort.dir === 'asc' ? 'desc' : 'asc';
        else _sort = { col, dir: 'asc' };
        this.renderTable();
      });
    });

    document.getElementById('histExportBtn')?.addEventListener('click', () => this.exportCsv());
    this.renderTable();
  },

  _filteredSorted() {
    return DB.dbGetAll('jobs')
      .filter((job) => {
        const q = Math.round(Number(job.quality_score || 0) * 100);
        if (_filters.status && job.status !== _filters.status) return false;
        if (_filters.model && job.model !== _filters.model) return false;
        if (q < _filters.minQuality || q > _filters.maxQuality) return false;
        return true;
      })
      .sort((a, b) => {
        const av = sortableValue(a, _sort.col);
        const bv = sortableValue(b, _sort.col);
        if (av < bv) return _sort.dir === 'asc' ? -1 : 1;
        if (av > bv) return _sort.dir === 'asc' ? 1 : -1;
        return 0;
      });
  },

  renderTable() {
    const all = this._filteredSorted();
    const start = (_page - 1) * _perPage;
    const rows = all.slice(start, start + _perPage);
    const body = document.getElementById('histBody');
    if (!body) return;

    body.innerHTML = rows.length ? rows.map((job) => {
      const book = DB.dbGet('books', job.book_id);
      const q = Math.round(Number(job.quality_score || 0) * 100);
      return `
        <tr>
          <td>${book?.title || `Book ${job.book_id}`}</td>
          <td><span class="tag tag-model">${job.model || '-'}</span></td>
          <td>${job.variant || 1}</td>
          <td><span class="tag ${statusClass(job.status)}">${job.status}</span></td>
          <td><div>${q}%</div><div class="quality-bar"><div class="quality-fill ${q >= 75 ? 'high' : (q >= 50 ? 'medium' : 'low')}" style="width:${q}%"></div></div></td>
          <td>$${Number(job.cost_usd || 0).toFixed(4)}</td>
          <td>${formatDate(job.created_at)}</td>
        </tr>
      `;
    }).join('') : '<tr><td colspan="7" class="text-muted">No matching rows.</td></tr>';

    this.renderPagination(all.length);
  },

  renderPagination(totalRows) {
    const pages = Math.max(1, Math.ceil(totalRows / _perPage));
    if (_page > pages) _page = pages;
    const el = document.getElementById('histPagination');
    if (!el) return;

    const btn = (label, target, active = false) => `<button ${active ? 'class="active"' : ''} data-page="${target}">${label}</button>`;
    let html = btn('Prev', Math.max(1, _page - 1));
    for (let p = 1; p <= pages; p += 1) {
      if (p <= 2 || p > pages - 2 || Math.abs(p - _page) <= 1) html += btn(String(p), p, p === _page);
    }
    html += btn('Next', Math.min(pages, _page + 1));
    el.innerHTML = html;
    el.querySelectorAll('button[data-page]').forEach((b) => {
      b.addEventListener('click', () => {
        _page = Number(b.dataset.page);
        this.renderTable();
      });
    });
  },

  exportCsv() {
    const all = this._filteredSorted();
    const header = ['Book', 'Model', 'Variant', 'Status', 'Quality%', 'Cost', 'Date'];
    const rows = all.map((job) => {
      const book = DB.dbGet('books', job.book_id);
      return [
        book?.title || `Book ${job.book_id}`,
        job.model || '',
        job.variant || 1,
        job.status || '',
        Math.round(Number(job.quality_score || 0) * 100),
        Number(job.cost_usd || 0).toFixed(4),
        job.created_at || '',
      ];
    });
    const csv = [header, ...rows]
      .map((row) => row.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'alexandria-history.csv';
    a.click();
  },
};
