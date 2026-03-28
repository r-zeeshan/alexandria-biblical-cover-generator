window.Pages = window.Pages || {};

function esc(str) {
  return String(str || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

const PROMPT_CATALOG = 'biblical';
const PROMPT_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'alexandria', label: 'Alexandria' },
  { id: 'winner', label: 'Winners' },
];
let activePromptFilter = 'all';

function promptApi(path = '') {
  const suffix = path ? `/${String(path).replace(/^\/+/, '')}` : '';
  return `/api/prompts${suffix}?catalog=${encodeURIComponent(PROMPT_CATALOG)}`;
}

function normalizedCategory(value) {
  return String(value || '').trim().toLowerCase();
}

function hasTag(prompt, tag) {
  const needle = String(tag || '').trim().toLowerCase();
  if (!needle) return false;
  return (Array.isArray(prompt?.tags) ? prompt.tags : [])
    .map((item) => String(item || '').trim().toLowerCase())
    .includes(needle);
}

function promptMatchesFilter(prompt) {
  if (activePromptFilter === 'winner') return normalizedCategory(prompt?.category) === 'winner';
  if (activePromptFilter === 'alexandria') return hasTag(prompt, 'alexandria');
  return true;
}

function hasReusablePlaceholder(template) {
  const text = String(template || '');
  return ['{title}', '{author}', '{TITLE}', '{AUTHOR}', '{SUBTITLE}', '{SCENE}', '{MOOD}', '{ERA}']
    .some((token) => text.includes(token));
}

window.Pages.prompts = {
  async render() {
    await DB.loadPrompts(PROMPT_CATALOG);
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="card">
        <div class="flex justify-between mb-8">
          <h3 class="card-title">Prompt Templates</h3>
          <div class="flex gap-8">
            <button class="btn btn-secondary" id="promptSeedBtn">Seed Built-in Prompts</button>
            <button class="btn btn-primary" id="promptNewBtn">+ New Prompt</button>
          </div>
        </div>
        <div class="filters-bar mb-8" id="promptFilterBar">
          ${PROMPT_FILTERS.map((filter) => `<button class="filter-chip ${filter.id === activePromptFilter ? 'active' : ''}" data-prompt-filter="${esc(filter.id)}">${esc(filter.label)}</button>`).join('')}
        </div>
        <div class="grid-3" id="promptGrid"></div>
      </div>
    `;

    document.getElementById('promptSeedBtn')?.addEventListener('click', () => this.seedBuiltins());
    document.getElementById('promptNewBtn')?.addEventListener('click', () => this.openPromptModal(null));
    content.querySelectorAll('[data-prompt-filter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activePromptFilter = String(btn.dataset.promptFilter || 'all').trim().toLowerCase() || 'all';
        content.querySelectorAll('[data-prompt-filter]').forEach((node) => node.classList.toggle('active', node === btn));
        this.renderGrid();
      });
    });
    this.renderGrid();
  },

  renderGrid() {
    const grid = document.getElementById('promptGrid');
    if (!grid) return;
    const prompts = DB.dbGetAll('prompts')
      .filter((prompt) => promptMatchesFilter(prompt))
      .sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime());

    if (!prompts.length) {
      grid.innerHTML = '<div class="text-muted">No prompts saved yet.</div>';
      return;
    }

    grid.innerHTML = prompts.map((prompt) => `
      <div class="prompt-card">
        <div class="flex justify-between">
          <span class="fw-600">${esc(prompt.name)}</span>
          <span class="tag tag-style">${esc(prompt.category || 'Saved')}</span>
        </div>
        <p class="text-sm text-muted mt-8">${esc((prompt.prompt_template || '').slice(0, 140))}${(prompt.prompt_template || '').length > 140 ? '...' : ''}</p>
        <div class="text-xs text-muted">usage ${Number(prompt.usage_count || 0)} | wins ${Number(prompt.win_count || 0)}</div>
        <div class="flex gap-4 mt-8">
          <button class="btn btn-sm btn-secondary" data-edit="${esc(prompt.id)}">Edit</button>
          <button class="btn btn-sm btn-danger" data-delete="${esc(prompt.id)}">Delete</button>
        </div>
      </div>
    `).join('');

    grid.querySelectorAll('[data-edit]').forEach((btn) => {
      btn.addEventListener('click', () => this.openPromptModal(DB.dbGet('prompts', btn.dataset.edit)));
    });

    grid.querySelectorAll('[data-delete]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        await this.deletePrompt(btn.dataset.delete);
      });
    });
  },

  openPromptModal(existing) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    const isEdit = Boolean(existing && existing.id);

    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header"><h2 class="modal-title">${isEdit ? 'Edit Prompt' : 'New Prompt'}</h2><button class="close-btn">x</button></div>
        <div class="modal-body">
          <div class="form-group"><label class="form-label">Name</label><input id="promptName" class="form-input" value="${esc(existing?.name || '')}" /></div>
          <div class="form-group"><label class="form-label">Category</label>
            <select id="promptCategory" class="form-select">
              ${['general', 'builtin', 'winner', 'Saved', 'Cossacks/Military', 'Classical Library', 'Wildcard'].map((c) => `<option value="${c}" ${existing?.category === c ? 'selected' : ''}>${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group"><label class="form-label">Template</label><textarea id="promptTemplate" class="form-textarea" rows="6">${esc(existing?.prompt_template || '')}</textarea></div>
          <div class="form-group"><label class="form-label">Negative Prompt</label><textarea id="promptNegative" class="form-textarea" rows="3">${esc(existing?.negative_prompt || '')}</textarea></div>
          <div class="form-group"><label class="form-label">Style Anchor IDs (comma separated)</label><input id="promptAnchors" class="form-input" value="${esc((existing?.style_anchors || []).join(', '))}" /></div>
          <div class="card">
            <div class="form-row">
              <input id="previewTitle" class="form-input" placeholder="Book title" value="Moby Dick" />
              <input id="previewAuthor" class="form-input" placeholder="Author" value="Herman Melville" />
            </div>
            <p class="text-sm mt-8" id="previewOutput"></p>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-secondary" id="promptCancelBtn">Cancel</button>
          <button class="btn btn-primary" id="promptSaveBtn">Save</button>
        </div>
      </div>
    `;

    const close = () => overlay.remove();
    const updatePreview = () => {
      const t = overlay.querySelector('#promptTemplate').value || '';
      const title = overlay.querySelector('#previewTitle').value || 'Book';
      const author = overlay.querySelector('#previewAuthor').value || 'Author';
      overlay.querySelector('#previewOutput').textContent = t.replaceAll('{title}', title).replaceAll('{author}', author);
    };

    ['#promptTemplate', '#previewTitle', '#previewAuthor'].forEach((sel) => {
      overlay.querySelector(sel).addEventListener('input', updatePreview);
    });

    overlay.querySelector('.close-btn')?.addEventListener('click', close);
    overlay.querySelector('#promptCancelBtn')?.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

    overlay.querySelector('#promptSaveBtn')?.addEventListener('click', async () => {
      const payload = {
        name: overlay.querySelector('#promptName').value.trim(),
        category: overlay.querySelector('#promptCategory').value || 'general',
        prompt_template: overlay.querySelector('#promptTemplate').value.trim(),
        negative_prompt: overlay.querySelector('#promptNegative').value.trim(),
        style_anchors: overlay.querySelector('#promptAnchors').value.split(',').map((s) => s.trim()).filter(Boolean),
      };
      if (!payload.name || !payload.prompt_template) {
        Toast.warning('Name and template are required.');
        return;
      }
      if (normalizedCategory(payload.category) !== 'winner' && !hasReusablePlaceholder(payload.prompt_template)) {
        Toast.warning('Reusable prompts should include at least one supported placeholder.');
        return;
      }

      try {
        let resp;
        if (isEdit) {
          resp = await fetch(promptApi(existing.id), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'update', ...payload }),
          });
        } else {
          resp = await fetch(promptApi(), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
        }
        if (!resp?.ok) {
          throw new Error(`HTTP ${resp?.status || 500}`);
        }
        await DB.loadPrompts(PROMPT_CATALOG);
        this.renderGrid();
        Toast.success('Prompt saved');
        close();
      } catch (err) {
        Toast.error(`Prompt save failed: ${err.message || err}`);
      }
    });

    updatePreview();
    document.body.appendChild(overlay);
  },

  async deletePrompt(promptId) {
    if (!promptId) return;
    try {
      const resp = await fetch(promptApi(promptId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete' }),
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      await DB.loadPrompts(PROMPT_CATALOG);
      this.renderGrid();
      Toast.success('Prompt deleted');
    } catch (err) {
      Toast.error(`Prompt delete failed: ${err.message || err}`);
    }
  },

  async seedBuiltins() {
    const now = new Date().toISOString();
    const existing = DB.dbGetAll('prompts');
    const existingAnchors = new Set();
    existing.forEach((row) => {
      (Array.isArray(row.style_anchors) ? row.style_anchors : []).forEach((anchor) => existingAnchors.add(String(anchor)));
    });

    const styles = (window.StyleDiversifier?.STYLE_POOL || []).slice(0, 10);
    let created = 0;

    for (const style of styles) {
      if (!style?.id || existingAnchors.has(style.id)) continue;
      const template = window.StyleDiversifier.buildDiversifiedPrompt('{title}', '{author}', style);
      const payload = {
        name: style.label,
        category: 'builtin',
        prompt_template: template,
        negative_prompt: 'text, letters, words, typography, logos, labels, watermark, signature, border, frame, ribbon, plaque',
        style_anchors: [style.id],
        quality_score: 0.82,
        source_model: 'seeded-client',
        notes: `Seeded from STYLE_POOL on ${now}.`,
      };

      try {
        const resp = await fetch(promptApi(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (resp.ok) {
          created += 1;
        }
      } catch {
        // Continue seeding the remaining styles.
      }
    }

    await DB.loadPrompts(PROMPT_CATALOG);
    this.renderGrid();
    Toast.success(`${created} prompt template${created === 1 ? '' : 's'} seeded`);
  },
};
