(function() {
  window.exportPlaybook = async function(symbol, strategyName) {
    try {
      const response = await fetch(`/api/export-playbook/${symbol}/${strategyName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await response.json();
      if (data.status === 'success') {
        document.getElementById('playbookCodeViewer').textContent = data.code;
        document.getElementById('playbookCopyBtn').onclick = () => {
          navigator.clipboard.writeText(data.code).then(() => {
            alert("Playbook Python code copied to clipboard!");
          }).catch(err => {
            alert("Failed to copy code: " + err);
          });
        };
        document.getElementById('tourOverlay').classList.add('active');
        document.getElementById('playbookExportModal').classList.add('active');
      } else {
        alert("Failed to export: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Error exporting playbook: " + err.message);
    }
  };

  window.closePlaybookExport = function() {
    document.getElementById('tourOverlay').classList.remove('active');
    document.getElementById('playbookExportModal').classList.remove('active');
  };
})();
