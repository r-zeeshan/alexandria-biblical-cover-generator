window.Pages = window.Pages || {};

let _search = '';
let _searchTimeout = null;

window.Pages.catalogs = {
  async render() {
    let books = DB.dbGetAll('books');
    if (!books.length) books = await DB.loadBooks('biblical');

    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="card">
        <div class="flex justify-between mb-8" style="gap:8px">
          <div class="form-group" style="flex:1;margin:0">
            <input class="form-input" id="catalogSearch" placeholder="Search books..." />
          </div>
          <button class="btn btn-secondary" id="catalogSyncBtn">🔄 Sync from Drive</button>
        </div>
        <span class="text-muted" id="catalogCount">${books.length} books</span>
      </div>
      <div class="grid-auto" id="catalogGrid"></div>
    `;

    document.getElementById('catalogSearch')?.addEventListener('input', (e) => {
      clearTimeout(_searchTimeout);
      _searchTimeout = setTimeout(() => {
        _search = String(e.target.value || '').trim().toLowerCase();
        this.renderGrid();
      }, 300);
    });

    document.getElementById('catalogSyncBtn')?.addEventListener('click', async () => {
      const btn = document.getElementById('catalogSyncBtn');
      btn.disabled = true;
      btn.textContent = 'Syncing...';
      try {
        const synced = await Drive.syncCatalog();
        Toast.success(`Catalog synced: ${synced.length} books`);
        this.render();
      } catch (err) {
        Toast.error(`Sync failed: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Sync from Drive';
      }
    });

    this.renderGrid();
  },

  renderGrid() {
    const grid = document.getElementById('catalogGrid');
    const count = document.getElementById('catalogCount');
    if (!grid) return;

    let books = DB.dbGetAll('books');
    if (_search) {
      books = books.filter((book) => {
        const txt = `${book.title} ${book.author} ${book.folder_name}`.toLowerCase();
        return txt.includes(_search);
      });
    }

    if (count) count.textContent = `${books.length} books`;
    if (!books.length) {
      grid.innerHTML = '<div class="text-muted">No books found.</div>';
      return;
    }

    const apiKey = DB.getSetting('google_api_key');
    grid.innerHTML = books
      .sort((a, b) => Number(a.number || 0) - Number(b.number || 0))
      .map((book) => `
        <div class="book-card" data-book-detail="${book.id}">
          <img class="book-thumb" src="${book.cover_jpg_id ? Drive.getDriveThumbnailUrl(book.cover_jpg_id, apiKey, 280) : (book.original || '')}" loading="lazy" />
          <div class="book-info">
            <div class="book-title">${book.title}</div>
            <div class="book-author">${book.author || ''}</div>
            <div class="book-author">#${book.number || book.id}</div>
          </div>
        </div>
      `).join('');

    grid.querySelectorAll('[data-book-detail]').forEach((el) => {
      el.addEventListener('click', () => this.showDetail(Number(el.dataset.bookDetail)));
    });
  },

  showDetail(bookId) {
    const book = DB.dbGet('books', bookId);
    if (!book) return;
    const winner = DB.dbGet('winners', bookId);
    const variants = DB.dbGetByIndex('jobs', 'book_id', bookId).filter((j) => j.status === 'completed').length;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header"><h2 class="modal-title">${book.number}. ${book.title}</h2><button class="close-btn">×</button></div>
        <div class="modal-body">
          <div class="grid-2">
            <div><img src="${book.cover_jpg_id ? Drive.getDriveThumbnailUrl(book.cover_jpg_id, DB.getSetting('google_api_key'), 500) : (book.original || '')}" style="width:220px;max-width:100%;border-radius:8px;border:1px solid var(--border)" /></div>
            <div>
              <div><span class="text-sm text-muted">Author</span><div>${book.author || '-'}</div></div>
              <div class="mt-8"><span class="text-sm text-muted">Number</span><div>${book.number || '-'}</div></div>
              <div class="mt-8"><span class="text-sm text-muted">Folder</span><div>${book.folder_name || '-'}</div></div>
              <div class="mt-8"><span class="text-sm text-muted">Cover File</span><div>${book.cover_jpg_id || '-'}</div></div>
              <div class="mt-8"><span class="text-sm text-muted">Synced At</span><div>${book.synced_at ? formatDate(book.synced_at) : '-'}</div></div>
              <div class="mt-8"><span class="text-sm text-muted">Variants</span><div>${variants}</div></div>
              <div class="mt-8">${winner ? '<span class="tag tag-gold">Winner selected</span>' : '<span class="tag tag-status">No winner</span>'}</div>
              <a class="btn btn-primary mt-16" href="#iterate" id="goIterateBtn">Generate Covers →</a>
            </div>
          </div>
        </div>
      </div>
    `;
    const close = () => overlay.remove();
    overlay.querySelector('.close-btn')?.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    overlay.querySelector('#goIterateBtn')?.addEventListener('click', () => {
      window.__ITERATE_BOOK_ID__ = book.id;
      close();
    });
    document.body.appendChild(overlay);
  },
};
