window.Pages = window.Pages || {};

function esc(str) {
  return String(str || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function modelLabel(modelId) {
  const model = OpenRouter.MODELS.find((m) => m.id === modelId);
  return model?.label || modelId || 'unknown';
}

window.Pages.dashboard = {
  async render() {
    const content = document.getElementById('content');

    const jobs = DB.dbGetAll('jobs');
    const ledger = DB.dbGetAll('cost_ledger');
    const winners = DB.dbGetAll('winners');
    const booksCount = DB.dbCount('books');

    const spent = ledger.reduce((sum, row) => sum + Number(row.cost_usd || 0), 0);
    const budget = Number(DB.getSetting('budget_limit', 50));
    const completedJobs = jobs.filter((j) => j.status === 'completed');
    const avgQuality = completedJobs.length
      ? completedJobs.reduce((sum, j) => sum + Number(j.quality_score || 0), 0) / completedJobs.length
      : 0;

    const byModel = new Map();
    ledger.forEach((row) => {
      const key = row.model || 'unknown';
      const value = byModel.get(key) || { model: key, jobs: 0, cost: 0, qualitySum: 0 };
      value.jobs += 1;
      value.cost += Number(row.cost_usd || 0);
      const job = DB.dbGet('jobs', row.job_id);
      value.qualitySum += Number(job?.quality_score || 0);
      byModel.set(key, value);
    });

    const recentActivity = jobs
      .filter((j) => ['completed', 'failed'].includes(j.status))
      .sort((a, b) => new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
      .slice(0, 8);

    const budgetPct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : 0;

    content.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi-card"><div class="kpi-label">Total Spent</div><div class="kpi-value">$${spent.toFixed(2)}</div><div class="progress-bar mt-8"><div class="progress-fill ${budgetPct > 90 ? 'danger' : ''}" style="width:${budgetPct}%"></div></div><div class="kpi-sub">$${spent.toFixed(2)} of $${budget.toFixed(2)} budget used</div></div>
        <div class="kpi-card"><div class="kpi-label">Books in Catalog</div><div class="kpi-value">${booksCount}</div></div>
        <div class="kpi-card"><div class="kpi-label">Avg Quality</div><div class="kpi-value">${Math.round(avgQuality * 100)}%</div></div>
        <div class="kpi-card"><div class="kpi-label">Total Images</div><div class="kpi-value">${completedJobs.length}</div></div>
        <div class="kpi-card"><div class="kpi-label">Approved</div><div class="kpi-value">${winners.length}</div></div>
      </div>

      <div class="card">
        <div class="card-header"><h3 class="card-title">Latest Generated Covers</h3><span class="text-muted" id="dashboardRecentStatus">Loading latest generations...</span></div>
        <div class="grid-auto" id="dashboardRecentGrid"></div>
      </div>

      <div class="grid-2">
        <div class="card">
          <h3 class="card-title mb-8">Model Breakdown</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Model</th><th>Jobs</th><th>Cost</th><th>Avg Quality</th></tr></thead>
              <tbody>
                ${[...byModel.values()].map((row) => `<tr><td>${esc(modelLabel(row.model))}</td><td>${row.jobs}</td><td>$${row.cost.toFixed(3)}</td><td>${Math.round((row.qualitySum / Math.max(1, row.jobs)) * 100)}%</td></tr>`).join('') || '<tr><td colspan="4" class="text-muted">No cost entries yet.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <h3 class="card-title mb-8">Recent Activity</h3>
          <div>
            ${recentActivity.map((job) => {
              const book = DB.dbGet('books', job.book_id);
              return `<div class="activity-item"><div class="activity-dot ${job.status === 'failed' ? 'failed' : ''}"></div><div><div class="activity-text">${esc(book?.title || `Book ${job.book_id}`)} - ${esc(modelLabel(job.model))} (${esc(job.status)})</div><div class="activity-time">${timeAgo(job.completed_at || job.created_at)}</div></div></div>`;
            }).join('') || '<p class="text-muted">No activity yet.</p>'}
          </div>
        </div>
      </div>
    `;

    let recentFromApi = [];
    try {
      const response = await fetch('/api/dashboard-data?catalog=biblical', { cache: 'no-store' });
      if (response.ok) {
        const payload = await response.json();
        recentFromApi = Array.isArray(payload.recent_results) ? payload.recent_results : [];
      }
    } catch {
      recentFromApi = [];
    }

    const fallbackLocal = this._fallbackRecentFromLocalJobs(18);
    this._renderRecentResults(recentFromApi, fallbackLocal);
  },

  _fallbackRecentFromLocalJobs(limit = 12) {
    const jobs = DB.dbGetAll('jobs')
      .filter((job) => job.status === 'completed' && (job.composited_image_blob || job.generated_image_blob))
      .sort((a, b) => new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
      .slice(0, Math.max(1, Number(limit || 12)));

    return jobs.map((job) => {
      const book = DB.dbGet('books', job.book_id);
      const composite = getBlobUrl(job.composited_image_blob || job.generated_image_blob, `${job.id}-dash-composite`);
      const raw = getBlobUrl(job.generated_image_blob || job.composited_image_blob, `${job.id}-dash-raw`);
      return {
        id: job.id,
        source: 'local',
        book_title: book?.title || `Book ${job.book_id}`,
        book_number: Number(book?.number || job.book_id || 0),
        model: job.model,
        quality_score: Number(job.quality_score || 0),
        cost: Number(job.cost_usd || 0),
        timestamp: job.completed_at || job.created_at,
        image_url: composite,
        raw_url: raw,
        prompt: String(job.prompt || ''),
      };
    });
  },

  _renderRecentResults(apiRows, fallbackRows) {
    const status = document.getElementById('dashboardRecentStatus');
    const grid = document.getElementById('dashboardRecentGrid');
    if (!status || !grid) return;

    const rows = Array.isArray(apiRows) && apiRows.length ? apiRows : fallbackRows;
    if (!rows.length) {
      status.textContent = 'No generated covers found yet.';
      grid.innerHTML = '<div class="text-muted">No generated covers found yet.</div>';
      return;
    }

    const usingFallback = !(Array.isArray(apiRows) && apiRows.length);
    status.textContent = usingFallback
      ? `Showing ${rows.length} latest generated cover(s) from local jobs.`
      : `Showing ${rows.length} latest generated cover(s).`;

    grid.innerHTML = rows.map((row, idx) => {
      const image = String(row.image_url || row.thumbnail_url || '').trim();
      const quality = Number(row.quality_score || 0);
      const id = String(row.id || `${row.book_number}-${row.model}-${row.variant || idx}`);
      return `
        <div class="result-card" data-recent-id="${esc(id)}">
          <img class="thumb" src="${esc(image)}" alt="${esc(row.book_title || 'cover')}" />
          <div class="card-body">
            <div class="flex justify-between">
              <span class="tag tag-model">${esc(modelLabel(row.model))}</span>
              <span class="tag tag-success">${quality > 0 ? `${Math.round(quality * 100)}%` : 'n/a'}</span>
            </div>
            <div class="card-meta">${esc(row.book_title || 'Unknown title')}</div>
            <div class="card-meta">$${Number(row.cost || 0).toFixed(3)} · ${formatDate(row.timestamp || new Date().toISOString())}</div>
          </div>
        </div>
      `;
    }).join('');

    const rowById = new Map();
    rows.forEach((row, idx) => {
      const id = String(row.id || `${row.book_number}-${row.model}-${row.variant || idx}`);
      rowById.set(id, row);
    });

    grid.querySelectorAll('[data-recent-id]').forEach((card) => {
      card.addEventListener('click', () => {
        const row = rowById.get(card.dataset.recentId);
        if (row) this._openRecentPreview(row);
      });
    });
  },

  _openRecentPreview(item) {
    const composite = String(item.image_url || item.thumbnail_url || '').trim();
    const raw = String(item.raw_url || item.image_url || item.thumbnail_url || '').trim();
    if (!composite && !raw) return;

    const state = { mode: 'composite' };
    const overlay = document.createElement('div');
    overlay.className = 'view-modal';
    overlay.innerHTML = `
      <div class="view-modal-inner">
        <div class="modal-header">
          <h3 class="modal-title">${esc(item.book_title || 'Generated Cover')} · ${esc(modelLabel(item.model))}</h3>
          <button class="close-btn" id="dashPreviewClose">x</button>
        </div>
        <div class="modal-body">
          <div class="tabs">
            <button class="tab active" data-mode="composite">Composite</button>
            <button class="tab" data-mode="raw">Raw</button>
          </div>
          <img id="dashPreviewImg" src="${esc(composite || raw)}" style="width:100%;height:auto;border-radius:8px;border:1px solid var(--border)" />
        </div>
      </div>
    `;

    const update = () => {
      const current = state.mode === 'composite' ? (composite || raw) : (raw || composite);
      overlay.querySelector('#dashPreviewImg').src = current;
      overlay.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.mode === state.mode));
    };

    overlay.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        state.mode = tab.dataset.mode;
        update();
      });
    });

    overlay.querySelector('#dashPreviewClose')?.addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  },
};
