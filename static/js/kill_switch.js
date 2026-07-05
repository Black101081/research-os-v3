(function() {
  window.triggerKillSwitch = async function() {
    const confirmation = prompt("WARNING: Are you sure you want to activate EMERGENCY STOP? Open positions will be closed immediately.\n\nTo confirm, please type 'CONFIRM':");
    if (confirmation !== 'CONFIRM') {
      alert("Emergency Stop cancelled.");
      return;
    }
    
    // Generate simple idempotency token
    const idempotencyToken = 'ks_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10);
    
    try {
      const response = await fetch('/api/kill-switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Token': idempotencyToken
        },
        body: JSON.stringify({
          confirm: 'CONFIRM',
          idempotency_token: idempotencyToken
        })
      });
      const data = await response.json();
      if (data.status === 'success') {
        if (typeof window.tick === 'function') window.tick();
        alert(data.message);
      } else {
        alert("Failed to activate Kill Switch: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Error triggering Kill Switch: " + err.message);
    }
  };

  window.toggleTradingMode = async function() {
    try {
      const response = await fetch('/api/toggle-trading-mode', { method: 'POST' });
      const data = await response.json();
      if (data.status === 'success') {
        if (typeof window.tick === 'function') window.tick();
      } else {
        alert("Failed to toggle mode: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Error toggling mode: " + err.message);
    }
  };
})();
