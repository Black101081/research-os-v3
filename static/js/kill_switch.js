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

  window.triggerResetKillSwitch = async function() {
    const confirmation = prompt("To confirm resetting Emergency Stop and restoring the system to active state, please type 'RESET':");
    if (confirmation !== 'RESET') {
      alert("Reset cancelled.");
      return;
    }
    
    try {
      const response = await fetch('/api/kill-switch/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'RESET' })
      });
      const data = await response.json();
      if (data.status === 'success') {
        if (typeof window.tick === 'function') window.tick();
        alert(data.message);
      } else {
        alert("Failed to reset Kill Switch: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Error resetting Kill Switch: " + err.message);
    }
  };

  window.toggleTradingMode = async function() {
    const confirmation = prompt("WARNING: You are about to toggle the trading mode. To confirm, please type 'TOGGLE':");
    if (confirmation !== 'TOGGLE') {
      alert("Toggling trading mode cancelled.");
      return;
    }

    try {
      const response = await fetch('/api/toggle-trading-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'TOGGLE' })
      });
      const data = await response.json();
      if (data.status === 'success') {
        if (typeof window.tick === 'function') window.tick();
        alert("Trading mode changed to: " + data.trading_mode.toUpperCase());
      } else {
        alert("Failed to toggle mode: " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Error toggling mode: " + err.message);
    }
  };
})();
