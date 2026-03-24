window.Pages = window.Pages || {};

let _costTimelineChart;
let _costModelChart;
let _qualityHistChart;
let _genTimelineChart;

function destroyCharts() {
  _costTimelineChart?.destroy();
  _costModelChart?.destroy();
  _qualityHistChart?.destroy();
  _genTimelineChart?.destroy();
}

function dateKey(iso) {
  return new Date(iso).toISOString().slice(0, 10);
}

window.Pages.analytics = {
  async render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="grid-2">
        <div class="card"><h3 class="card-title">Daily Cost (Last 30 Days)</h3><div class="chart-container"><canvas id="costTimelineChart"></canvas></div></div>
        <div class="card"><h3 class="card-title">Cost by Model</h3><div class="chart-container"><canvas id="costModelChart"></canvas></div></div>
      </div>
      <div class="grid-2">
        <div class="card"><h3 class="card-title">Quality Distribution</h3><div class="chart-container"><canvas id="qualityHistChart"></canvas></div></div>
        <div class="card"><h3 class="card-title">Generations Per Day (Last 30 Days)</h3><div class="chart-container"><canvas id="genTimelineChart"></canvas></div></div>
      </div>
      <div class="card"><h3 class="card-title">Model Comparison</h3><div class="table-wrap"><table><thead><tr><th>Model</th><th>Total</th><th>Completed</th><th>Failed</th><th>Avg Quality</th><th>Avg Cost</th><th>Total Cost</th></tr></thead><tbody id="analyticsModelBody"></tbody></table></div></div>
    `;
    this.renderChartsAndTable();
  },

  renderChartsAndTable() {
    destroyCharts();

    const jobs = DB.dbGetAll('jobs');
    const ledger = DB.dbGetAll('cost_ledger');
    const now = new Date();
    const days = [...Array(30)].map((_, idx) => {
      const d = new Date(now);
      d.setDate(now.getDate() - (29 - idx));
      return d.toISOString().slice(0, 10);
    });

    const costByDay = new Map(days.map((d) => [d, 0]));
    ledger.forEach((row) => {
      const d = dateKey(row.recorded_at || row.created_at || new Date().toISOString());
      if (costByDay.has(d)) costByDay.set(d, costByDay.get(d) + Number(row.cost_usd || 0));
    });

    const byModelCost = new Map();
    ledger.forEach((row) => {
      const model = row.model || 'unknown';
      byModelCost.set(model, (byModelCost.get(model) || 0) + Number(row.cost_usd || 0));
    });

    const bins = new Array(10).fill(0);
    jobs.filter((j) => j.status === 'completed').forEach((job) => {
      const q = Math.max(0, Math.min(99, Math.floor(Number(job.quality_score || 0) * 100)));
      const index = Math.floor(q / 10);
      bins[index] += 1;
    });

    const gensByDay = new Map(days.map((d) => [d, 0]));
    jobs.forEach((job) => {
      const d = dateKey(job.created_at || new Date().toISOString());
      if (gensByDay.has(d)) gensByDay.set(d, gensByDay.get(d) + 1);
    });

    _costTimelineChart = new Chart(document.getElementById('costTimelineChart'), {
      type: 'bar',
      data: { labels: days, datasets: [{ label: 'Cost', data: days.map((d) => Number(costByDay.get(d).toFixed(4))), backgroundColor: 'rgba(197,165,90,0.7)' }] },
      options: { responsive: true, maintainAspectRatio: false },
    });

    const pieLabels = [...byModelCost.keys()];
    const pieValues = pieLabels.map((k) => Number(byModelCost.get(k).toFixed(4)));
    _costModelChart = new Chart(document.getElementById('costModelChart'), {
      type: 'doughnut',
      data: {
        labels: pieLabels,
        datasets: [{
          data: pieValues,
          backgroundColor: ['#c5a55a', '#1a2744', '#22c55e', '#ef4444', '#3b82f6', '#8b5cf6', '#f97316', '#ec4899'],
        }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    _qualityHistChart = new Chart(document.getElementById('qualityHistChart'), {
      type: 'bar',
      data: {
        labels: ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100'],
        datasets: [{ label: 'Jobs', data: bins, backgroundColor: 'rgba(34,197,94,0.7)' }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    _genTimelineChart = new Chart(document.getElementById('genTimelineChart'), {
      type: 'line',
      data: {
        labels: days,
        datasets: [{ label: 'Generations', data: days.map((d) => gensByDay.get(d)), borderColor: '#3b82f6', fill: false }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    const byModel = new Map();
    jobs.forEach((job) => {
      const model = job.model || 'unknown';
      const row = byModel.get(model) || { model, total: 0, completed: 0, failed: 0, qualitySum: 0, qualityCount: 0, costSum: 0 };
      row.total += 1;
      if (job.status === 'completed') {
        row.completed += 1;
        row.qualitySum += Number(job.quality_score || 0);
        row.qualityCount += 1;
      }
      if (job.status === 'failed') row.failed += 1;
      row.costSum += Number(job.cost_usd || 0);
      byModel.set(model, row);
    });

    const body = document.getElementById('analyticsModelBody');
    body.innerHTML = [...byModel.values()].map((row) => `
      <tr>
        <td>${row.model}</td>
        <td>${row.total}</td>
        <td>${row.completed}</td>
        <td>${row.failed}</td>
        <td>${Math.round((row.qualitySum / Math.max(1, row.qualityCount)) * 100)}%</td>
        <td>$${(row.costSum / Math.max(1, row.total)).toFixed(4)}</td>
        <td>$${row.costSum.toFixed(4)}</td>
      </tr>
    `).join('') || '<tr><td colspan="7" class="text-muted">No analytics yet.</td></tr>';
  },
};
