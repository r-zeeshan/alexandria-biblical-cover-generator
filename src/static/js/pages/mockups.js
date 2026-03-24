window.Pages = window.Pages || {};

function selectedCoverOptions() {
  const winners = DB.dbGetAll('winners').map((w) => {
    const job = DB.dbGet('jobs', w.job_id);
    const book = DB.dbGet('books', w.book_id);
    if (!job || !book) return null;
    return {
      key: `winner:${book.id}`,
      label: `${book.title} (winner)`,
      src: getBlobUrl(job.composited_image_blob || job.generated_image_blob, `${job.id}-mock-w`),
      book,
      job,
    };
  }).filter(Boolean);

  const recent = DB.dbGetAll('jobs')
    .filter((j) => j.status === 'completed' && j.composited_image_blob)
    .sort((a, b) => new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
    .slice(0, 10)
    .map((job) => {
      const book = DB.dbGet('books', job.book_id);
      return {
        key: `recent:${job.id}`,
        label: `${book?.title || `Book ${job.book_id}`} — ${job.model}`,
        src: getBlobUrl(job.composited_image_blob, `${job.id}-mock-r`),
        book,
        job,
      };
    });

  return { winners, recent };
}

window.Pages.mockups = {
  async render() {
    const content = document.getElementById('content');
    const options = selectedCoverOptions();

    content.innerHTML = `
      <div class="card">
        <div class="form-group" style="margin-bottom:0">
          <label class="form-label">Select Cover</label>
          <select id="mockupSelect" class="form-select">
            <option value="">— Select —</option>
            <optgroup label="Winners">${options.winners.map((o) => `<option value="${o.key}">${o.label}</option>`).join('')}</optgroup>
            <optgroup label="Recent">${options.recent.map((o) => `<option value="${o.key}">${o.label}</option>`).join('')}</optgroup>
          </select>
        </div>
      </div>
      <div class="grid-3 hidden" id="mockupGrid"></div>
      <div class="card hidden" id="mockupDetails"></div>
    `;

    document.getElementById('mockupSelect')?.addEventListener('change', (e) => {
      const key = e.target.value;
      const selected = [...options.winners, ...options.recent].find((o) => o.key === key);
      this.renderPreview(selected);
    });
  },

  renderPreview(selected) {
    const grid = document.getElementById('mockupGrid');
    const details = document.getElementById('mockupDetails');
    if (!grid || !details) return;

    if (!selected) {
      grid.classList.add('hidden');
      details.classList.add('hidden');
      return;
    }

    grid.classList.remove('hidden');
    details.classList.remove('hidden');

    grid.innerHTML = `
      <div class="card"><h4>Thumbnail (200px)</h4><img src="${selected.src}" style="max-width:200px;width:100%;height:auto" /></div>
      <div class="card"><h4>Print Preview (400px)</h4><img src="${selected.src}" style="max-width:400px;width:100%;height:auto" /></div>
      <div class="card"><h4>Full Size</h4><div style="max-height:400px;overflow:auto"><img src="${selected.src}" style="max-width:100%;height:auto" /></div></div>
    `;

    details.innerHTML = `
      <h3 class="card-title">Details</h3>
      <div class="grid-2 mt-8">
        <div><div class="text-sm text-muted">Title</div><div>${selected.book?.title || '-'}</div></div>
        <div><div class="text-sm text-muted">Author</div><div>${selected.book?.author || '-'}</div></div>
        <div><div class="text-sm text-muted">Model</div><div>${selected.job?.model || '-'}</div></div>
        <div><div class="text-sm text-muted">Quality</div><div>${Math.round(Number(selected.job?.quality_score || 0) * 100)}%</div></div>
        <div><div class="text-sm text-muted">Cost</div><div>$${Number(selected.job?.cost_usd || 0).toFixed(3)}</div></div>
        <div><div class="text-sm text-muted">Generated</div><div>${selected.job?.completed_at ? formatDate(selected.job.completed_at) : '-'}</div></div>
      </div>
      <button class="btn btn-primary mt-16" id="mockupDownloadBtn">⬇ Download Full Size</button>
    `;

    document.getElementById('mockupDownloadBtn')?.addEventListener('click', () => {
      const a = document.createElement('a');
      a.href = selected.src;
      a.download = `${selected.book?.number || 'book'}-mockup.jpg`;
      a.click();
    });
  },
};
