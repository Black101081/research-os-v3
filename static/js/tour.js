(function() {
  let currentTourStep = 0;
  const tourSteps = [
    {
      title: "Real-time Ingestion Pipeline",
      content: `
        <p><strong>Step 1: Real-time Ingestion</strong></p>
        <p style="margin-top: 8px;">The pipeline starts with high-frequency live WebSockets streaming trade ticks and raw order books directly from the exchange. Each tick triggers immediate processing and is routed to memory caches for feature calculation.</p>
        <p style="margin-top: 6px; color: var(--primary);">Key Component: <code>HyperliquidWSClient</code></p>
      `
    },
    {
      title: "Incremental Feature Calculations",
      content: `
        <p><strong>Step 2: Factors & Indicators</strong></p>
        <p style="margin-top: 8px;">Raw ticks are converted into OHLCV bars. The OS computes high-frequency factors (like returns, volatility, z-scores) and indicators (like MACD, Bollinger Bands) incrementally using high-speed vector math under 5ms.</p>
        <p style="margin-top: 6px; color: var(--primary);">Key Component: <code>ResearchEngine</code></p>
      `
    },
    {
      title: "Security Gateways & Validator",
      content: `
        <p><strong>Step 3: Validation Gating & Decay</strong></p>
        <p style="margin-top: 8px;">Before any strategy candidate can trigger an order, it must pass the live execution gate. This confirms the spec file has not decayed and satisfies code verification hashes.</p>
        <p style="margin-top: 6px; color: var(--primary);">Key Component: <code>ValidatorRunner</code></p>
      `
    },
    {
      title: "Event-Driven Backtest Sandbox",
      content: `
        <p><strong>Step 4: High-Fidelity Simulation</strong></p>
        <p style="margin-top: 8px;">Each candidate goes through rigorous event-driven backtesting simulating historical market phases, modeling realistic transaction fees and slippage to ensure profitability.</p>
        <p style="margin-top: 6px; color: var(--primary);">Key Component: <code>BaselineBacktestRunner</code></p>
      `
    },
    {
      title: "Composite Scoring & Cockpit Control",
      content: `
        <p><strong>Step 5: Ranking & Playbook Decision</strong></p>
        <p style="margin-top: 8px;">Strategies are ranked using a multi-factor Composite Score. Researchers can review detailed Research Briefs, write comments, and submit GO/NOGO decisions directly to the OS to override the status on the board.</p>
        <p style="margin-top: 6px; color: var(--primary);">Key Component: <code>Research Cockpit (UI Drawer)</code></p>
      `
    }
  ];

  window.startGuidedTour = function() {
    currentTourStep = 0;
    document.getElementById('tourOverlay').classList.add('active');
    document.getElementById('tourModal').classList.add('active');
    renderTourStep();
  };

  window.closeGuidedTour = function() {
    document.getElementById('tourOverlay').classList.remove('active');
    document.getElementById('tourModal').classList.remove('active');
  };

  window.nextTourStep = function() {
    if (currentTourStep < tourSteps.length - 1) {
      currentTourStep++;
      renderTourStep();
    } else {
      closeGuidedTour();
    }
  };

  window.prevTourStep = function() {
    if (currentTourStep > 0) {
      currentTourStep--;
      renderTourStep();
    }
  };

  function renderTourStep() {
    const step = tourSteps[currentTourStep];
    document.getElementById('tourStepTitle').textContent = step.title;
    document.getElementById('tourStepContent').innerHTML = step.content;
    document.getElementById('tourStepIndicator').textContent = `${currentTourStep + 1} / ${tourSteps.length}`;
    
    const prevBtn = document.getElementById('tourPrevBtn');
    const nextBtn = document.getElementById('tourNextBtn');
    
    prevBtn.style.opacity = currentTourStep === 0 ? '0.4' : '1';
    prevBtn.disabled = currentTourStep === 0;
    
    nextBtn.textContent = currentTourStep === tourSteps.length - 1 ? 'Finish' : 'Next';
  }
})();
