window.Pages = window.Pages || {};

const tabContent = {
  db: `
    <h3>Database</h3>
    <p class="text-muted">In-memory stores mimic IndexedDB and are exposed via <span class="code-inline">window.DB</span>.</p>
    <div class="table-wrap"><table><thead><tr><th>Store</th><th>Key path</th><th>Auto increment</th></tr></thead><tbody>
      <tr><td>books</td><td>id</td><td>No</td></tr>
      <tr><td>jobs</td><td>id</td><td>No</td></tr>
      <tr><td>winners</td><td>book_id</td><td>No</td></tr>
      <tr><td>prompts</td><td>id</td><td>Yes</td></tr>
      <tr><td>settings</td><td>key</td><td>No</td></tr>
      <tr><td>cost_ledger</td><td>id</td><td>Yes</td></tr>
      <tr><td>batches</td><td>id</td><td>No</td></tr>
    </tbody></table></div>
    <pre class="code-block">DB.dbPut(store, item)
DB.dbGet(store, key)
DB.dbGetAll(store)
DB.dbGetByIndex(store, index, value)
DB.setSetting(key, value)
DB.getSetting(key, fallback)</pre>
  `,
  drive: `
    <h3>Drive API</h3>
    <p class="text-muted">Drive helper methods power catalog sync and cover preview loading.</p>
    <pre class="code-block">Drive.syncCatalog(progressCb)
Drive.catalogCacheStatus()
Drive.loadCachedCatalog()
Drive.refreshCatalogCache()
Drive.downloadCoverForBook(bookNumber)
Drive.listDriveSubfolders(folderId, apiKey)</pre>
    <p>Primary backend endpoints:</p>
    <ul>
      <li><span class="code-inline">GET /api/iterate-data</span></li>
      <li><span class="code-inline">GET /api/drive/status</span></li>
      <li><span class="code-inline">GET /api/drive/input-covers</span></li>
      <li><span class="code-inline">GET /api/books/{book}/cover-preview</span></li>
    </ul>
  `,
  openrouter: `
    <h3>OpenRouter</h3>
    <p class="text-muted">Model registry and generation adapter.</p>
    <pre class="code-block">OpenRouter.init()
OpenRouter.MODELS
OpenRouter.MODEL_COSTS
OpenRouter.generateImage(prompt, model, apiKey, signal, timeoutMs, opts)</pre>
    <p>Generation is executed via backend queue endpoint <span class="code-inline">POST /api/generate</span> with polling against <span class="code-inline">GET /api/jobs/{id}</span>.</p>
  `,
  compositor: `
    <h3>Compositor</h3>
    <p class="text-muted">Covers are 3784×2777 and medallion defaults are cx=2850, cy=1350, radius=520.</p>
    <pre class="code-block">Compositor.smartComposite({ coverImg, generatedImg, cx, cy, radius })</pre>
    <p>Mask path: <span class="code-inline">/static/img/medallion_mask.png</span></p>
  `,
  quality: `
    <h3>Quality</h3>
    <p class="text-muted">7-factor weighted score:</p>
    <div class="table-wrap"><table><thead><tr><th>Factor</th><th>Weight</th></tr></thead><tbody>
      <tr><td>Edge</td><td>0.25</td></tr>
      <tr><td>Center-of-mass</td><td>0.20</td></tr>
      <tr><td>Circular fit</td><td>0.20</td></tr>
      <tr><td>Color richness</td><td>0.12</td></tr>
      <tr><td>Brightness</td><td>0.08</td></tr>
      <tr><td>Contrast</td><td>0.08</td></tr>
      <tr><td>Diversity</td><td>0.07</td></tr>
    </tbody></table></div>
    <pre class="code-block">Quality.scoreGeneratedImage(image)
Quality.getDetailedScores(image)</pre>
  `,
  jobs: `
    <h3>Job Queue</h3>
    <p class="text-muted">Client queue state machine with heartbeat and retries.</p>
    <pre class="code-block">JobQueue.add(job)
JobQueue.addBatch(jobs)
JobQueue.pause() / resume()
JobQueue.abortJob(jobId)
JobQueue.cancelAll()
JobQueue.onChange(listener)
JobQueue._heartbeat()</pre>
    <p>Pipeline: <span class="code-inline">downloading_cover</span> → <span class="code-inline">generating</span> → <span class="code-inline">scoring</span> → <span class="code-inline">compositing</span> → <span class="code-inline">completed</span></p>
  `,
};

window.Pages['api-docs'] = {
  async render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="card">
        <div class="tabs" id="apiDocTabs">
          <button class="tab active" data-tab="db">Database</button>
          <button class="tab" data-tab="drive">Drive API</button>
          <button class="tab" data-tab="openrouter">OpenRouter</button>
          <button class="tab" data-tab="compositor">Compositor</button>
          <button class="tab" data-tab="quality">Quality</button>
          <button class="tab" data-tab="jobs">Job Queue</button>
        </div>
        <div id="apiDocContent"></div>
      </div>
    `;

    const renderTab = (tab) => {
      document.querySelectorAll('#apiDocTabs .tab').forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === tab));
      document.getElementById('apiDocContent').innerHTML = tabContent[tab] || '<p class="text-muted">No documentation for this tab.</p>';
    };

    document.querySelectorAll('#apiDocTabs .tab').forEach((btn) => {
      btn.addEventListener('click', () => renderTab(btn.dataset.tab));
    });

    renderTab('db');
  },
};
