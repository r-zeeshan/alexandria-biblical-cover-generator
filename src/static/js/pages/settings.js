window.Pages = window.Pages || {};

function applyMedallionPreview() {
  const cx = Number(document.getElementById('setMedCx')?.value || 2850);
  const cy = Number(document.getElementById('setMedCy')?.value || 1350);
  const radius = Number(document.getElementById('setMedRadius')?.value || 520);
  const circle = document.getElementById('medallionCircle');
  if (!circle) return;
  const previewW = 300;
  const previewH = 220;
  const coverW = 3784;
  const coverH = 2777;
  const px = (cx / coverW) * previewW;
  const py = (cy / coverH) * previewH;
  const pr = (radius / coverW) * previewW;
  circle.style.left = `${px - pr}px`;
  circle.style.top = `${py - pr}px`;
  circle.style.width = `${pr * 2}px`;
  circle.style.height = `${pr * 2}px`;
}

function wireSave(id, key, parse = (v) => v) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener('change', () => {
    DB.setSetting(key, parse(el.value));
    if (id.startsWith('setMed')) applyMedallionPreview();
    if (id === 'setQualThresh') {
      const val = Math.round(Number(el.value || 0) * 100);
      const out = document.getElementById('setQualVal');
      if (out) out.textContent = `${val}%`;
    }
    Toast.success('Settings saved');
    updateHeader();
  });
}

window.Pages.settings = {
  async render() {
    const content = document.getElementById('content');
    const threshold = Number(DB.getSetting('quality_threshold', 0.6));

    content.innerHTML = `
      <div class="settings-grid">
        <div class="settings-section">
          <h3 class="card-title mb-8">API Keys</h3>
          <div class="form-group"><label class="form-label">OpenRouter Key</label><input type="password" id="setOrKey" class="form-input" value="${DB.getSetting('openrouter_key', '')}" /></div>
          <div class="form-group"><label class="form-label">Google API Key</label><input type="password" id="setGoogleKey" class="form-input" value="${DB.getSetting('google_api_key', '')}" /></div>
          <div class="flex gap-8"><button class="btn btn-secondary" id="testOpenRouterBtn">Test OpenRouter</button><button class="btn btn-secondary" id="testGoogleBtn">Test Google Drive</button></div>
        </div>

        <div class="settings-section">
          <h3 class="card-title mb-8">Google Drive</h3>
          <div class="form-group"><label class="form-label">Source Folder ID</label><input id="setDriveSource" class="form-input" value="${DB.getSetting('drive_source_folder', '')}" /></div>
          <div class="form-group"><label class="form-label">Output Folder ID</label><input id="setDriveOutput" class="form-input" value="${DB.getSetting('drive_output_folder', '')}" /></div>
          <div class="form-group"><label class="form-label">Winner Folder ID</label><input id="setDriveWinner" class="form-input" value="${DB.getSetting('drive_winner_folder', '')}" /></div>
          <button class="btn btn-secondary" id="openDriveSourceBtn">Open Drive Source</button>
        </div>

        <div class="settings-section">
          <h3 class="card-title mb-8">Generation Defaults</h3>
          <div class="form-group"><label class="form-label">Budget Limit ($)</label><input type="number" id="setBudget" class="form-input" value="${DB.getSetting('budget_limit', 50)}" /></div>
          <div class="form-group"><label class="form-label">Default Variant Count</label><select id="setVariants" class="form-select">${Array.from({ length: 10 }, (_, i) => `<option value="${i + 1}" ${Number(DB.getSetting('default_variant_count', 1)) === i + 1 ? 'selected' : ''}>${i + 1}</option>`).join('')}</select></div>
          <div class="form-group"><label class="form-label">Quality Threshold</label><input type="range" min="0" max="1" step="0.05" id="setQualThresh" class="w-full" value="${threshold}" /><span id="setQualVal" class="text-muted">${Math.round(threshold * 100)}%</span></div>
        </div>

        <div class="settings-section">
          <h3 class="card-title mb-8">Medallion Position</h3>
          <p class="text-sm text-muted">Cover dimensions: 3784×2777px. Medallion is on the front panel (right side).</p>
          <div class="form-row">
            <div class="form-group"><label class="form-label">Center X</label><input type="number" id="setMedCx" class="form-input" value="${DB.getSetting('medallion_cx', 2850)}" /></div>
            <div class="form-group"><label class="form-label">Center Y</label><input type="number" id="setMedCy" class="form-input" value="${DB.getSetting('medallion_cy', 1350)}" /></div>
          </div>
          <div class="form-group"><label class="form-label">Radius</label><input type="number" id="setMedRadius" class="form-input" value="${DB.getSetting('medallion_radius', 520)}" /></div>
          <div style="position:relative;width:300px;height:220px;border:1px solid var(--border);background:#f8fafc;border-radius:8px;overflow:hidden">
            <div id="medallionCircle" style="position:absolute;border:2px solid var(--gold);border-radius:50%;background:rgba(197,165,90,0.12)"></div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3 class="card-title mb-8">Actions</h3>
        <div class="flex gap-8" style="flex-wrap:wrap">
          <button class="btn btn-danger" id="setResetBtn">Reset to Defaults</button>
          <button class="btn btn-secondary" id="setSeedPromptsBtn">Seed Prompts</button>
          <button class="btn btn-secondary" id="setSyncCatalogBtn">Sync Catalog Now</button>
        </div>
      </div>
    `;

    wireSave('setOrKey', 'openrouter_key');
    wireSave('setGoogleKey', 'google_api_key');
    wireSave('setDriveSource', 'drive_source_folder');
    wireSave('setDriveOutput', 'drive_output_folder');
    wireSave('setDriveWinner', 'drive_winner_folder');
    wireSave('setBudget', 'budget_limit', (v) => Number(v));
    wireSave('setVariants', 'default_variant_count', (v) => Number(v));
    wireSave('setQualThresh', 'quality_threshold', (v) => Number(v));
    wireSave('setMedCx', 'medallion_cx', (v) => Number(v));
    wireSave('setMedCy', 'medallion_cy', (v) => Number(v));
    wireSave('setMedRadius', 'medallion_radius', (v) => Number(v));

    applyMedallionPreview();

    document.getElementById('testOpenRouterBtn')?.addEventListener('click', async () => {
      try {
        await OpenRouter.init();
        Toast.success(`OpenRouter models loaded: ${OpenRouter.MODELS.length}`);
      } catch (err) {
        Toast.error(`OpenRouter test failed: ${err.message}`);
      }
    });

    document.getElementById('testGoogleBtn')?.addEventListener('click', async () => {
      try {
        const folders = await Drive.listDriveSubfolders(DB.getSetting('drive_source_folder'), DB.getSetting('google_api_key'));
        Toast.success(`Drive test ok: ${folders.length} items`);
      } catch (err) {
        Toast.error(`Google Drive test failed: ${err.message}`);
      }
    });

    document.getElementById('openDriveSourceBtn')?.addEventListener('click', () => {
      const folder = DB.getSetting('drive_source_folder', '');
      window.open(`https://drive.google.com/drive/folders/${encodeURIComponent(folder)}`, '_blank');
    });

    document.getElementById('setResetBtn')?.addEventListener('click', async () => {
      DB.dbClear('settings');
      try {
        await fetch('/cgi-bin/settings.py/reset', { method: 'POST' });
      } catch {
        // ignore
      }
      await DB.initDefaults();
      Toast.success('Settings reset');
      this.render();
    });

    document.getElementById('setSeedPromptsBtn')?.addEventListener('click', () => {
      window.Pages.prompts.seedBuiltins();
    });

    document.getElementById('setSyncCatalogBtn')?.addEventListener('click', async () => {
      try {
        const books = await Drive.syncCatalog();
        Toast.success(`Catalog synced: ${books.length} books`);
      } catch (err) {
        Toast.error(`Sync failed: ${err.message}`);
      }
    });
  },
};
