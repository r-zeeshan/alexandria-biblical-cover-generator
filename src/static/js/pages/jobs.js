window.Pages = window.Pages || {};

let _refreshInterval = null;

function modelLabel(id) {
  return OpenRouter.MODELS.find((m) => m.id === id)?.label || id;
}

function retryJob(job) {
  const clone = {
    ...job,
    id: uuid(),
    status: 'queued',
    error: null,
    started_at: null,
    completed_at: null,
    cost_usd: 0,
    quality_score: null,
    created_at: new Date().toISOString(),
  };
  DB.dbPut('jobs', clone);
  JobQueue.add(clone);
}

window.Pages.jobs = {
  async render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="kpi-grid" id="jobsKpiGrid"></div>
      <div class="card">
        <div class="flex gap-8">
          <button class="btn btn-secondary" id="jobsPauseBtn">Pause Queue</button>
          <button class="btn btn-danger" id="jobsClearBtn">Clear Queue</button>
        </div>
      </div>
      <div class="card" id="jobsRunningCard"></div>
      <div class="card"><div class="card-header"><h3 class="card-title">Queued Jobs</h3></div><div class="table-wrap"><table><thead><tr><th>#</th><th>Book</th><th>Model</th><th>Variant</th><th>Queued At</th><th>Actions</th></tr></thead><tbody id="jobsQueuedBody"></tbody></table></div></div>
      <div class="card"><div class="card-header"><h3 class="card-title">Recent Jobs</h3></div><div class="table-wrap"><table><thead><tr><th>Book</th><th>Model</th><th>Variant</th><th>Status</th><th>Quality</th><th>Cost</th><th>Completed</th><th>Actions</th></tr></thead><tbody id="jobsRecentBody"></tbody></table></div></div>
    `;

    const pauseBtn = document.getElementById('jobsPauseBtn');
    const clearBtn = document.getElementById('jobsClearBtn');

    pauseBtn?.addEventListener('click', () => {
      if (JobQueue.paused) JobQueue.resume();
      else JobQueue.pause();
      pauseBtn.textContent = JobQueue.paused ? 'Resume Queue' : 'Pause Queue';
      this.renderInner();
    });
    clearBtn?.addEventListener('click', () => JobQueue.cancelAll());

    this.renderInner();
    _refreshInterval = setInterval(() => this.renderInner(), 3000);
    window.addEventListener('hashchange', () => this.cleanup(), { once: true });
  },

  cleanup() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  },

  renderInner() {
    const allJobs = DB.dbGetAll('jobs');
    const queueJobs = JobQueue.queue;
    const runningJobs = [...JobQueue.running.values()].map((entry) => entry.job);
    const completed = allJobs.filter((j) => j.status === 'completed').length;
    const failed = allJobs.filter((j) => j.status === 'failed').length;

    const kpi = document.getElementById('jobsKpiGrid');
    if (kpi) {
      kpi.innerHTML = `
        <div class="kpi-card"><div class="kpi-label">Queue</div><div class="kpi-value">${queueJobs.length}</div></div>
        <div class="kpi-card"><div class="kpi-label">Running</div><div class="kpi-value">${runningJobs.length}</div></div>
        <div class="kpi-card"><div class="kpi-label">Completed</div><div class="kpi-value">${completed}</div></div>
        <div class="kpi-card"><div class="kpi-label">Failed</div><div class="kpi-value">${failed}</div></div>
      `;
    }

    const runningCard = document.getElementById('jobsRunningCard');
    if (runningCard) {
      if (!runningJobs.length) {
        runningCard.innerHTML = '<div class="card-header"><h3 class="card-title">Currently Running</h3></div><p class="text-muted">No running jobs.</p>';
      } else {
        runningCard.innerHTML = `<div class="card-header"><h3 class="card-title">Currently Running</h3></div>${runningJobs.map((job) => {
          const book = DB.dbGet('books', job.book_id);
          return `<div class="pipeline-row"><span>${book?.title || `Book ${job.book_id}`}</span><span>${modelLabel(job.model)}</span><span>${job.status}</span><span>${job._elapsed || 0}s</span></div>`;
        }).join('')}`;
      }
    }

    const qBody = document.getElementById('jobsQueuedBody');
    if (qBody) {
      qBody.innerHTML = queueJobs.length ? queueJobs.map((job, idx) => {
        const book = DB.dbGet('books', job.book_id);
        return `<tr><td>${idx + 1}</td><td>${book?.title || `Book ${job.book_id}`}</td><td>${modelLabel(job.model)}</td><td>${job.variant}</td><td>${formatDate(job.created_at)}</td><td><button class="btn-cancel-job" data-job-cancel="${job.id}">Cancel</button></td></tr>`;
      }).join('') : '<tr><td colspan="6" class="text-muted">Queue is empty.</td></tr>';
      qBody.querySelectorAll('[data-job-cancel]').forEach((btn) => {
        btn.addEventListener('click', () => JobQueue.abortJob(btn.dataset.jobCancel));
      });
    }

    const rBody = document.getElementById('jobsRecentBody');
    if (rBody) {
      const rows = allJobs
        .filter((j) => ['completed', 'failed', 'cancelled'].includes(j.status))
        .sort((a, b) => new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
        .slice(0, 20);
      rBody.innerHTML = rows.length ? rows.map((job) => {
        const book = DB.dbGet('books', job.book_id);
        return `<tr>
          <td>${book?.title || `Book ${job.book_id}`}</td>
          <td>${modelLabel(job.model)}</td>
          <td>${job.variant}</td>
          <td><span class="tag ${job.status === 'completed' ? 'tag-success' : 'tag-failed'}">${job.status}</span></td>
          <td>${Math.round(Number(job.quality_score || 0) * 100)}%</td>
          <td>$${Number(job.cost_usd || 0).toFixed(3)}</td>
          <td>${job.completed_at ? formatDate(job.completed_at) : '-'}</td>
          <td>${job.status === 'failed' ? `<button class="btn btn-sm btn-secondary" data-job-retry="${job.id}">Retry</button>` : ''}</td>
        </tr>`;
      }).join('') : '<tr><td colspan="8" class="text-muted">No jobs yet.</td></tr>';

      rBody.querySelectorAll('[data-job-retry]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const job = DB.dbGet('jobs', btn.dataset.jobRetry);
          if (job) retryJob(job);
        });
      });
    }
  },
};
