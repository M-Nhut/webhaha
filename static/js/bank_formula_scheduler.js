/* Formula work for question banks: viewport first, one block per idle task. */
window.BankFormulaScheduler = (() => {
  'use strict';
  const selector = '[data-bank-lazy-formulas]';
  const records = new Map();
  const queue = new Set();
  let observer, mutations, task, timer, running = false, paused = false;
  let waitingSince = 0;

  const engineReady = () => typeof window.MathJax?.typesetPromise === 'function';
  const visible = el => {
    if (!el.isConnected || !el.getClientRects().length) return false;
    const rect = el.getBoundingClientRect();
    return rect.bottom >= -240 && rect.top <= window.innerHeight + 240;
  };
  const clearMath = roots => {
    if (window.MathJax?.typesetClear && roots.length) {
      try { window.MathJax.typesetClear(roots); } catch (_) { /* Engine may still be starting. */ }
    }
  };

  function init() {
    if (mutations) return;
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          const record = records.get(entry.target);
          if (!record) return;
          record.visible = entry.isIntersecting;
          if (record.visible && record.dirty) queue.add(entry.target);
          else if (!record.visible) queue.delete(entry.target);
        });
        schedule();
      }, {rootMargin: '240px 0px'});
    } else {
      window.addEventListener('scroll', refreshVisible, {capture: true, passive: true});
      window.addEventListener('resize', refreshVisible);
    }
    mutations = new MutationObserver(changes => {
      // Detached detail/editor blocks must not stay in the observer/queue.
      const removed = [];
      changes.forEach(change => change.removedNodes.forEach(node => {
        if (node.nodeType === 1 && !node.isConnected) removed.push(node);
      }));
      clearMath(removed);
      records.forEach((record, el) => {
        if (!el.isConnected) {
          observer?.unobserve(el);
          records.delete(el);
          queue.delete(el);
        }
      });
    });
    document.querySelectorAll(selector).forEach(zone => mutations.observe(zone, {childList: true, subtree: true}));
  }

  function refreshVisible() {
    records.forEach((record, el) => {
      record.visible = visible(el);
      if (record.visible && record.dirty) queue.add(el);
      else queue.delete(el);
    });
    schedule();
  }

  function observe(el, formulas = {}, options = {}) {
    init();
    let record = records.get(el);
    const explicitSource = Object.prototype.hasOwnProperty.call(options, 'source');
    const text = String(el.textContent || '');
    const source = explicitSource ? String(options.source || '')
      : record && (text === record.afterText || text === record.source) ? record.source : text;
    const merged = Object.assign({}, record?.formulas || {}, formulas);
    // Fingerprints contain only assets used by this block, not every answer.
    const referenced = new Set(Array.from(source.matchAll(/\[\[formula:([^\]]+)\]\]/g), match => match[1]));
    const relevant = {};
    Object.keys(merged).sort().forEach(id => {
      const asset = merged[id];
      if (referenced.has(id) || (asset.source_format === 'LaTeXBlock' && asset.source_text?.trim() && source.includes(asset.source_text.trim()))) {
        relevant[id] = asset;
      }
    });
    const signature = source + '\u0000' + JSON.stringify(relevant) + '\u0000' + engineReady();
    if (record?.signature === signature) {
      // Alpine can reset x-text to the same source after typesetting.
      if (record.done && el.querySelector('mjx-container, .formula-image, .formula-error, .tex-table-wrap')) return;
      if (record.done && text === record.afterText) return;
      if (!record.done) return;
    }
    if (!record) {
      record = {visible: visible(el)};
      records.set(el, record);
      observer?.observe(el);
    }
    Object.assign(record, {source, formulas: relevant, signature, dirty: true, done: false});
    if (record.visible) queue.add(el);
    schedule();
  }

  function schedule() {
    if (paused || running || task != null || timer != null || !queue.size) return;
    // Alpine runs before the local MathJax script. Wait briefly for startup
    // rather than caching a fallback caused only by script execution order.
    if (!engineReady()) {
      if (!waitingSince) waitingSince = performance.now();
      if (performance.now() - waitingSince < 5000) {
        timer = window.setTimeout(() => { timer = null; schedule(); }, 100);
        return;
      }
    }
    task = 'requestIdleCallback' in window
      ? window.requestIdleCallback(drain, {timeout: 120})
      : window.setTimeout(drain, 16);
  }

  async function drain() {
    task = null;
    if (paused) return;
    let el, record;
    for (const candidate of queue) {
      queue.delete(candidate);
      const current = records.get(candidate);
      if (!current || !current.dirty || !visible(candidate)) continue;
      el = candidate;
      record = current;
      break;
    }
    if (!el) { schedule(); return; }
    running = true;
    const signature = record.signature;
    const source = record.source;
    try {
      if (el.textContent !== source) {
        clearMath([el]);
        el.textContent = source;
      }
      await window.FormulaRenderer.renderFormulas(el, record.formulas, {immediate: true});
      if (record.signature === signature && el.isConnected) {
        record.afterText = el.textContent;
        record.dirty = false;
        record.done = true;
      }
    } catch (error) {
      console.warn('[BankFormulaScheduler]', error);
    } finally {
      running = false;
      schedule();
    }
  }

  function route(root, formulas, options) {
    if (options?.immediate || root.matches?.('[data-manual-preview]') || !document.querySelector(selector)) return false;
    const zone = root.closest?.(selector);
    if (!zone && !root.querySelector?.(selector)) return false;
    const targets = Array.from(root.querySelectorAll('.katex-render, [data-latex-answer], [data-manual-preview]'));
    if (root.matches?.('.katex-render, [data-latex-answer]')) targets.unshift(root);
    targets.forEach(el => {
      if (el.closest(selector) && !el.matches('[data-manual-preview]')) observe(el, formulas, el === root ? options : {});
      else window.FormulaRenderer.renderFormulas(el, formulas, {immediate: true});
    });
    return true;
  }

  window.addEventListener('pagehide', () => {
    paused = true;
    if (task != null) {
      if ('cancelIdleCallback' in window) window.cancelIdleCallback(task);
      else window.clearTimeout(task);
    }
    window.clearTimeout(timer);
    task = timer = null;
    queue.clear();
    observer?.disconnect();
    mutations?.disconnect();
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    paused = false;
    document.querySelectorAll(selector).forEach(zone => mutations?.observe(zone, {childList: true, subtree: true}));
    records.forEach((record, el) => { if (el.isConnected) observer?.observe(el); });
    refreshVisible();
  });

  return {route};
})();
