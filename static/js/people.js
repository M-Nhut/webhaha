/* Account fields keep the server contract; destructive actions use native confirmation. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-people-role]').forEach(select => {
    const fieldset = select.closest('form') || select.closest('fieldset');
    const label = fieldset?.querySelector('[data-people-position-label]');
    const update = () => { if (label) label.textContent = select.value === 'student' ? 'Lớp / Vị trí' : 'Vị trí'; };
    select.addEventListener('change', update);
    update();
  });
  document.querySelectorAll('[data-people-confirm]').forEach(form => {
    form.classList.add('has-people-confirm');
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.peopleConfirm)) event.preventDefault();
    });
  });
});
