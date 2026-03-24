window.Pages = window.Pages || {};

let _selectedBooks = [];

function getComparableBooks() {
  return DB.dbGetAll('books').filter((book) => DB.dbGetByIndex('jobs', 'book_id', book.id).some((j) => j.status === 'completed'));
}

window.Pages.compare = {
  async render() {
    const content = document.getElementById('content');
    const books = getComparableBooks();
    content.innerHTML = `
      <div class="card">
        <div class="card-header"><h3 class="card-title">Book Picker</h3></div>
        <div class="filters-bar" id="comparePicker">
          ${books.map((book) => `<button class="filter-chip" data-book-chip="${book.id}">${book.title.length > 20 ? `${book.title.slice(0, 20)}…` : book.title}</button>`).join('')}
        </div>
      </div>
      <div class="compare-grid" id="compareGrid"></div>
    `;

    content.querySelectorAll('[data-book-chip]').forEach((chip) => {
      chip.addEventListener('click', () => {
        const id = Number(chip.dataset.bookChip);
        if (_selectedBooks.includes(id)) {
          _selectedBooks = _selectedBooks.filter((v) => v !== id);
        } else if (_selectedBooks.length < 4) {
          _selectedBooks.push(id);
        } else {
          Toast.warning('Select up to 4 books.');
        }
        content.querySelectorAll('[data-book-chip]').forEach((c) => c.classList.toggle('active', _selectedBooks.includes(Number(c.dataset.bookChip))));
        this.renderCompareGrid();
      });
    });

    this.renderCompareGrid();
  },

  renderCompareGrid() {
    const grid = document.getElementById('compareGrid');
    if (!grid) return;
    if (!_selectedBooks.length) {
      grid.innerHTML = '<div class="text-muted">Select books to compare.</div>';
      return;
    }

    grid.style.gridTemplateColumns = `repeat(${_selectedBooks.length}, 1fr)`;
    grid.innerHTML = _selectedBooks.map((bookId) => {
      const book = DB.dbGet('books', bookId);
      const variants = DB.dbGetByIndex('jobs', 'book_id', bookId)
        .filter((j) => j.status === 'completed')
        .sort((a, b) => Number(b.quality_score || 0) - Number(a.quality_score || 0));
      return `
        <div class="card">
          <h4>${book?.title || `Book ${bookId}`}</h4>
          <div class="grid-auto">
            ${variants.map((job) => `
              <div class="result-card">
                <img class="thumb" src="${getBlobUrl(job.composited_image_blob || job.generated_image_blob, `${job.id}-cmp`)}" />
                <div class="card-body">
                  <div class="tag tag-model">${job.model}</div>
                  <div class="quality-meter mt-8"><div class="quality-bar"><div class="quality-fill ${Number(job.quality_score || 0) > 0.7 ? 'high' : (Number(job.quality_score || 0) > 0.5 ? 'medium' : 'low')}" style="width:${Math.round(Number(job.quality_score || 0) * 100)}%"></div></div></div>
                  <div class="card-meta">$${Number(job.cost_usd || 0).toFixed(3)} · ${Math.round(Number(job.quality_score || 0) * 100)}%</div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }).join('');
  },
};
