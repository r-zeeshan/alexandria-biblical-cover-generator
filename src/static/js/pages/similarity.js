window.Pages = window.Pages || {};

function getFingerprint(img) {
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 32;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, 0, 0, 32, 32);
  const data = ctx.getImageData(0, 0, 32, 32).data;
  const bins = new Array(48).fill(0);
  for (let i = 0; i < data.length; i += 4) {
    bins[Math.floor((data[i] / 256) * 16)] += 1;
    bins[16 + Math.floor((data[i + 1] / 256) * 16)] += 1;
    bins[32 + Math.floor((data[i + 2] / 256) * 16)] += 1;
  }
  const norm = Math.sqrt(bins.reduce((sum, v) => sum + v * v, 0));
  return bins.map((v) => v / (norm || 1));
}

function cosine(a, b) {
  let dot = 0;
  for (let i = 0; i < a.length; i += 1) dot += a[i] * b[i];
  return dot;
}

window.Pages.similarity = {
  async render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="card">
        <p>Detect potentially duplicate illustrations using 48-bin color histograms.</p>
        <div class="flex gap-8 items-center">
          <button class="btn btn-primary" id="simRunBtn">Run Similarity Check</button>
          <span class="text-muted" id="simStatus"></span>
        </div>
      </div>
      <div id="simResults"></div>
    `;

    document.getElementById('simRunBtn')?.addEventListener('click', () => this.runCheck());
  },

  async runCheck() {
    const status = document.getElementById('simStatus');
    const resultsEl = document.getElementById('simResults');
    const jobs = DB.dbGetAll('jobs').filter((j) => j.status === 'completed').slice(0, 50);
    if (jobs.length < 2) {
      Toast.info('Need at least 2 completed jobs.');
      return;
    }

    status.textContent = 'Computing fingerprints...';
    const fingerprints = [];
    for (const job of jobs) {
      const src = getBlobUrl(job.composited_image_blob || job.generated_image_blob, `${job.id}-sim`);
      try {
        const img = await loadImage(src);
        fingerprints.push({ job, vec: getFingerprint(img), src });
      } catch {
        // ignore broken rows
      }
    }

    status.textContent = 'Comparing pairs...';
    const pairs = [];
    for (let i = 0; i < fingerprints.length; i += 1) {
      for (let j = i + 1; j < fingerprints.length; j += 1) {
        const sim = cosine(fingerprints[i].vec, fingerprints[j].vec);
        if (sim > 0.85) pairs.push({ a: fingerprints[i], b: fingerprints[j], sim });
      }
    }

    status.textContent = `${pairs.length} potential duplicate pairs`;
    if (!pairs.length) {
      resultsEl.innerHTML = '<div class="card"><p class="text-muted">No high-similarity pairs found.</p></div>';
      return;
    }

    resultsEl.innerHTML = pairs.sort((x, y) => y.sim - x.sim).map((pair) => {
      const color = pair.sim > 0.95 ? '#ef4444' : '#eab308';
      const bookA = DB.dbGet('books', pair.a.job.book_id);
      const bookB = DB.dbGet('books', pair.b.job.book_id);
      return `
        <div class="card">
          <div class="flex gap-16 items-center">
            <img style="width:160px;border:3px solid ${color};border-radius:8px" src="${pair.a.src}" />
            <div class="text-muted" style="font-size:24px">↔</div>
            <img style="width:160px;border:3px solid ${color};border-radius:8px" src="${pair.b.src}" />
            <div>
              <div class="fw-600">${Math.round(pair.sim * 100)}%</div>
              <div class="text-sm text-muted">${bookA?.title || pair.a.job.book_id} vs ${bookB?.title || pair.b.job.book_id}</div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  },
};
