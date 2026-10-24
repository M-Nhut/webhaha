/* Phase 7: observed scores and mastery keep separate scales and missing values. */
(() => {
  'use strict';
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const valid = (value, min, max) => finite(value) && value >= min && value <= max ? value : null;
  function initPracticeProgressCharts(config = {}) {
    const history = Array.isArray(config.history) ? config.history : [];
    const mastery = Array.isArray(config.masteryHistory) ? config.masteryHistory : [];
    const cognitive = config.cognitiveMastery || {};
    const root = getComputedStyle(document.documentElement);
    const token = name => root.getPropertyValue(name).trim();
    const colors = {
      primary: token('--color-primary'), success: token('--color-success'),
      subtle: token('--color-primary-subtle'), text: token('--color-text-secondary'),
      border: token('--color-border'), surface: token('--color-surface')
    };
    const font = {family: token('--font-sans'), size: parseFloat(token('--size-xs')) || 14};
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fallback = (canvas, message) => {
      canvas.closest('.student-chart-frame').hidden = true;
      const notice = canvas.closest('.student-chart-panel').querySelector('[data-chart-fallback]');
      if (notice) { if (message) notice.textContent = message; notice.hidden = false; }
    };
    const chart = (id, values, labels, options) => {
      const canvas = document.getElementById(id);
      if (!canvas) return;
      if (!values.some(finite)) return fallback(canvas, 'Chưa có số liệu hợp lệ để vẽ biểu đồ. Bảng dữ liệu bên dưới giữ nguyên các bản ghi.');
      if (!window.Chart) return fallback(canvas);
      const isBar = options.type === 'bar';
      try {
        new window.Chart(canvas, {
          type: options.type || 'line',
          data: {
            labels,
            datasets: [{
              label: options.label, data: values, borderColor: options.color,
              backgroundColor: isBar ? options.color : colors.surface,
              borderWidth: 2, pointRadius: 4, pointHoverRadius: 6,
              pointBackgroundColor: options.color, pointStyle: options.pointStyle || 'circle',
              showLine: values.filter(finite).length >= 4, spanGaps: false, tension: 0,
              fill: false, maxBarThickness: 44
            }]
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            animation: reduced ? false : {duration: 150},
            color: colors.text,
            plugins: {
              legend: {display: false},
              tooltip: {titleFont: {...font, weight: '600'}, bodyFont: font, callbacks: {
                title: items => options.titles?.[items[0]?.dataIndex] || items[0]?.label || '',
                label: context => `${options.label}: ${context.parsed.y}${options.unit || ''}`
              }}
            },
            scales: {
              x: {grid: {display: false}, ticks: {font, color: colors.text, maxRotation: 0, autoSkip: !isBar, maxTicksLimit: isBar ? 4 : 8}, border: {color: colors.border}},
              y: {min: 0, max: options.max, title: {display: true, text: options.axisLabel, color: colors.text, font}, grid: {color: colors.border}, border: {display: false}, ticks: {font, color: colors.text, stepSize: options.step}}
            }
          }
        });
      } catch (_) { fallback(canvas); }
    };
    chart('scoreChart', history.map(item => valid(item.score, 0, 10)), history.map((_, index) => `Bài ${index + 1}`), {
      label: 'Điểm', max: 10, step: 2, axisLabel: 'Điểm (0–10)', color: colors.primary,
      titles: history.map(item => `${item.date} · ${item.title}`), unit: ' / 10'
    });
    chart('masteryChart', mastery.map(item => finite(item.mastery) ? valid(item.mastery / 100, 0, 1) : null), mastery.map((_, index) => `Lần ${index + 1}`), {
      label: 'Mức thành thạo', max: 1, step: .2, axisLabel: 'Mức thành thạo (0–1)', color: colors.success,
      titles: mastery.map(item => item.date), pointStyle: 'rectRot'
    });
    const levels = ['nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao'];
    chart('accuracyChart', levels.map(key => {
      const item = cognitive[key];
      return item && item.sample_count > 0 && finite(item.mastery) ? valid(item.mastery * 100, 0, 100) : null;
    }), [['Nhận', 'biết'], ['Thông', 'hiểu'], ['Vận', 'dụng'], ['Vận dụng', 'cao']], {
      type: 'bar', label: 'Kết quả tổng hợp', max: 100, step: 25,
      axisLabel: 'Tỷ lệ (%)', color: colors.primary, unit: '%',
      titles: ['Nhận biết', 'Thông hiểu', 'Vận dụng', 'Vận dụng cao']
    });
  }
  function start() {
    const data = document.getElementById('practice-progress-data');
    if (!data) return;
    try { initPracticeProgressCharts(JSON.parse(data.textContent)); }
    catch (_) { document.querySelectorAll('[data-chart-fallback]').forEach(node => {node.hidden = false;}); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
