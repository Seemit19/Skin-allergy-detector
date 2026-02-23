const analyzeForm = document.getElementById('analyze-form');
const issueInput = document.getElementById('issue');
const statusText = document.getElementById('status');
const analysisResult = document.getElementById('analysis-result');
const historyList = document.getElementById('history-list');

function toList(items = []) {
  if (!items.length) return '<li>Not available</li>';
  return items.map((x) => `<li>${x}</li>`).join('');
}

function renderAnalysis(data) {
  analysisResult.classList.remove('hidden');
  analysisResult.innerHTML = `
    <div class="result-box">
      <p><strong>Probable Allergy:</strong> ${data.probable_allergy}</p>
      <p><strong>Most Likely Cause:</strong> ${data.most_likely_cause}</p>
      <p><strong>Remedies:</strong></p>
      <ul>${toList(data.remedies)}</ul>
      <p><strong>Precautions:</strong></p>
      <ul>${toList(data.precautions)}</ul>
      <p><strong>Triggering Factors:</strong></p>
      <ul>${toList(data.triggering_factors)}</ul>
      <p><small>Saved at: ${new Date(data.created_at).toLocaleString()}</small></p>
    </div>
  `;
}

function renderHistory(items) {
  if (!items.length) {
    historyList.innerHTML = '<p>No allergy logs yet.</p>';
    return;
  }

  historyList.innerHTML = items
    .map(
      (item) => `
      <div class="history-item">
        <p><strong>${new Date(item.created_at).toLocaleString()}</strong></p>
        <p><strong>Issue:</strong> ${item.issue}</p>
        <p><strong>Probable Allergy:</strong> ${item.probable_allergy}</p>
        <p><strong>Cause:</strong> ${item.most_likely_cause}</p>
        <p><strong>Factors:</strong> ${(item.factors || []).join(', ') || 'N/A'}</p>
      </div>
    `,
    )
    .join('');
}

function renderFrequencyList(elementId, obj) {
  const target = document.getElementById(elementId);
  const entries = Object.entries(obj || {});
  if (!entries.length) {
    target.innerHTML = '<li>No data yet</li>';
    return;
  }
  target.innerHTML = entries.map(([k, v]) => `<li>${k}: ${v}</li>`).join('');
}

async function loadHistory() {
  const res = await fetch('/api/history');
  const data = await res.json();
  renderHistory(data);
}

async function loadReport() {
  const res = await fetch('/api/report');
  const data = await res.json();

  document.getElementById('report-summary').innerHTML = `<p><strong>Total Logged Issues:</strong> ${data.total_logs}</p>`;
  renderFrequencyList('allergy-frequency', data.allergy_frequency);
  renderFrequencyList('factor-frequency', data.factor_frequency);
  renderFrequencyList('daily-frequency', data.daily_frequency);
}

analyzeForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const issue = issueInput.value.trim();
  if (!issue) {
    statusText.textContent = 'Please describe your issue first.';
    return;
  }

  statusText.textContent = 'Analyzing with OpenAI...';

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ issue }),
    });

    const payload = await res.json();
    if (!res.ok) {
      statusText.textContent = payload.error || 'Failed to analyze issue.';
      return;
    }

    statusText.textContent = 'Analysis complete and log saved.';
    renderAnalysis(payload);
    issueInput.value = '';
    await Promise.all([loadHistory(), loadReport()]);
  } catch (err) {
    statusText.textContent = `Error: ${err.message}`;
  }
});

loadHistory();
loadReport();
