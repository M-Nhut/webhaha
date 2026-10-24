/* Overview motion follows the system preference and pauses in background tabs. */
(() => {
  const dashboard = document.querySelector('.academy-dashboard');
  if (!dashboard) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const render = () => {
    dashboard.dataset.dashboardMotion = reducedMotion.matches ? 'off' : 'running';
    dashboard.toggleAttribute('data-motion-suspended', document.hidden);
  };

  reducedMotion.addEventListener('change', render);
  document.addEventListener('visibilitychange', render);
  render();
})();
