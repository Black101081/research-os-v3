(function() {
  async function loadResearchPresets() {
    const container = document.getElementById('presetsContainer');
    if (!container) return;
    container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; padding: 24px;">Loading templates...</div>`;
    
    try {
      const response = await fetch('/api/presets');
      const presets = await response.json();
      
      if (!presets || !presets.length) {
        container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; padding: 24px;">No presets available.</div>`;
        return;
      }
      
      container.innerHTML = presets.map((p, idx) => `
        <div class="preset-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="badge badge-blue" style="font-size:0.65rem;">${p.category}</span>
            <span style="font-size:0.7rem; color:var(--muted); font-weight:700;">#${idx + 1}</span>
          </div>
          <h4 style="color:#fff; font-size:0.92rem; font-weight:700; margin:4px 0 2px 0;">${p.name}</h4>
          <p style="font-size:0.78rem; color:var(--text-muted); line-height:1.4; flex-grow:1;">${p.description}</p>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; padding-top:8px; border-top:1px dashed var(--border);">
            <span style="font-size:0.72rem; font-family:var(--font-mono); color:var(--primary); font-weight:700;">${p.spec.strategy_family}</span>
            <button class="tab-btn active" style="padding:4px 8px; font-size:0.7rem; border-radius:4px;" onclick="copyPresetSpec(${idx})">Copy Spec JSON</button>
          </div>
        </div>
      `).join('');
      
      window.cachedPresets = presets;
    } catch (err) {
      container.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1; padding: 24px; color:var(--error);">Failed to load presets: ${err.message}</div>`;
    }
  }

  window.loadResearchPresets = loadResearchPresets;

  window.copyPresetSpec = function(idx) {
    if (!window.cachedPresets || !window.cachedPresets[idx]) return;
    const specStr = JSON.stringify(window.cachedPresets[idx].spec, null, 2);
    navigator.clipboard.writeText(specStr).then(() => {
      alert("Strategy Spec JSON copied to clipboard!");
    }).catch(err => {
      alert("Failed to copy Spec: " + err);
    });
  };
})();
