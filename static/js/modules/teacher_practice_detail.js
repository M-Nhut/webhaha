/* Class-scoped source selection and native form validation; server owns generation. */
(() => {
  'use strict';
  const initTeacherPracticeFilters = () => {
    const form = document.getElementById('adaptive-practice-form');
    if (!form || form.dataset.initialized) return;
    form.dataset.initialized = 'true';
    const course = form.querySelector('#adaptive-course');
    const banks = [...form.querySelectorAll('.adaptive-bank')];
    const submit = form.querySelector('[data-teacher-generate]');
    const errors = form.querySelector('[data-teacher-form-errors]');
    const mixInputs = [...form.querySelectorAll('input[name^="mix_"]')];
    const mixTotal = form.querySelector('[data-teacher-mix-total]');
    const status = form.querySelector('[data-teacher-submit-status]');
    let busy = false;
    const refreshBanks = () => {
      const subject = course.options[course.selectedIndex]?.dataset.subject;
      let visibleCount = 0, removed = 0;
      banks.forEach(label => {
        let counts = {};
        try { counts = JSON.parse(label.dataset.courseCounts || '{}'); } catch (_error) { /* Invalid data remains unavailable. */ }
        const count = Number(counts[String(course.value)] || 0);
        const visible = label.dataset.subject === subject && count > 0;
        const input = label.querySelector('input');
        if (!visible && input.checked) removed++;
        label.hidden = !visible;
        input.disabled = !visible;
        if (!visible) input.checked = false;
        if (visible) { visibleCount++; label.querySelector('.bank-count').textContent = String(count); }
      });
      form.querySelector('[data-teacher-no-banks]').hidden = visibleCount > 0;
      form.querySelector('[data-teacher-source-status]').textContent = `${visibleCount} ngân hàng hợp lệ với lớp đang chọn.${removed ? ` Đã bỏ chọn ${removed} nguồn không còn hợp lệ.` : ''}`;
      submit.disabled = busy || visibleCount === 0;
    };
    const refreshMix = () => {
      const total = mixInputs.reduce((sum, input) => sum + (input.value === '' ? NaN : Number(input.value)), 0);
      const valid = Number.isFinite(total) && total === 100;
      mixTotal.textContent = `Tổng tỷ lệ: ${Number.isFinite(total) ? total + '%' : 'chưa đủ dữ liệu'}${valid ? '' : ' · Cần bằng 100%'}`;
      mixTotal.classList.toggle('is-invalid', !valid);
      return valid;
    };
    course.addEventListener('change', refreshBanks);
    mixInputs.forEach(input => input.addEventListener('input', refreshMix));
    form.addEventListener('input', event => event.target.removeAttribute('aria-invalid'));
    form.addEventListener('change', event => event.target.removeAttribute('aria-invalid'));
    form.addEventListener('submit', event => {
      if (busy) { event.preventDefault(); return; }
      const issues = [];
      form.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
      if (!banks.some(label => !label.hidden && label.querySelector('input').checked)) issues.push(['adaptive-banks', 'Chọn ít nhất một ngân hàng hợp lệ cho lớp nhận bài.']);
      if (!form.querySelector('input[name="cognitive_levels"]:checked')) issues.push(['adaptive-levels', 'Chọn ít nhất một mức nhận thức.']);
      if (!refreshMix()) { mixInputs.forEach(input => input.setAttribute('aria-invalid', 'true')); issues.push(['mix-weak', 'Tổng tỷ lệ vùng yếu, trung bình và duy trì phải bằng 100%.']); }
      const list = errors.querySelector('ul'); list.replaceChildren();
      issues.forEach(([id, message]) => {
        const item = document.createElement('li'), link = document.createElement('a');
        link.href = '#' + id; link.textContent = message;
        link.addEventListener('click', () => {
          const target = document.getElementById(id);
          (target.matches('input,select') ? target : target.querySelector('input:not(:disabled)'))?.focus();
        });
        item.append(link); list.append(item);
      });
      errors.hidden = issues.length === 0;
      if (issues.length) { event.preventDefault(); errors.focus(); return; }
      busy = true; submit.disabled = true; submit.setAttribute('aria-busy', 'true'); status.hidden = false;
    });
    window.addEventListener('pageshow', () => { busy = false; submit.removeAttribute('aria-busy'); status.hidden = true; refreshBanks(); });
    refreshBanks(); refreshMix();
  };
  const init = () => {
    initTeacherPracticeFilters();
    document.querySelectorAll('.teacher-disclosure').forEach(disclosure => disclosure.addEventListener('toggle', () => {
      if (disclosure.open) window.renderFormulas?.(disclosure, {}, {immediate: true});
    }));
    const printOpened = new Set();
    window.addEventListener('beforeprint', () => {
      document.querySelectorAll('.teacher-profile details').forEach(disclosure => {
        if (!disclosure.open) { printOpened.add(disclosure); disclosure.open = true; }
      });
    });
    window.addEventListener('afterprint', () => { printOpened.forEach(disclosure => { disclosure.open = false; }); printOpened.clear(); });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
