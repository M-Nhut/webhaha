import { icons } from './icons.js';

export function escapeHTML(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
export function icon(name, size = 18) {
  const key = name.includes('-') ? name.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('') : name[0].toUpperCase() + name.slice(1);
  const nodes = icons[key] || icons.CircleHelp;
  const attrs = obj => Object.entries(obj).map(([k, v]) => `${k}="${escapeHTML(v)}"`).join(' ');
  return `<svg width="${Number(size)}" height="${Number(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${nodes.map(([tag, a]) => `<${tag} ${attrs(a)}></${tag}>`).join('')}</svg>`;
}
export function badge(text, tone = 'neutral') {
  return `<span class="badge badge-${escapeHTML(tone)}">${escapeHTML(text)}</span>`;
}
export function button(label, action, variant = 'secondary', iconName = '') {
  return `<button type="button" class="btn btn-${escapeHTML(variant)}" data-action="${escapeHTML(action)}">${iconName ? icon(iconName) : ''}${escapeHTML(label)}</button>`;
}
let toastTimer;
export function toast(message) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 4500);
}
export function openDialog({ title, description = '', body = '', confirmLabel = 'Xác nhận', cancelLabel = 'Hủy', onConfirm, destructive = false }) {
  const opener = document.activeElement;
  const dialog = document.createElement('dialog');
  dialog.className = 'dialog';
  dialog.setAttribute('aria-labelledby', 'dialog-title');
  dialog.innerHTML = `<form method="dialog"><header class="dialog-header"><div><h2 id="dialog-title">${escapeHTML(title)}</h2>${description ? `<p class="text-muted">${escapeHTML(description)}</p>` : ''}</div><button type="button" class="icon-btn" data-close aria-label="Đóng hộp thoại">${icon('X')}</button></header><div class="dialog-body">${body}</div><p class="dialog-error text-danger" role="alert" hidden></p><footer class="dialog-footer"><button class="btn btn-secondary" type="button" data-close>${escapeHTML(cancelLabel)}</button><button class="btn btn-${destructive ? 'danger' : 'primary'}" type="submit">${escapeHTML(confirmLabel)}</button></footer></form>`;
  document.body.append(dialog);
  dialog.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
  dialog.querySelector('form').addEventListener('submit', async e => {
    e.preventDefault();
    const submit = e.submitter;
    submit.disabled = true;
    submit.setAttribute('aria-busy', 'true');
    try {
      const value = onConfirm ? await onConfirm(dialog) : true;
      if (value !== false) dialog.close('confirmed');
    } catch (error) {
      const msg = dialog.querySelector('.dialog-error');
      msg.textContent = error.message;
      msg.hidden = false;
    } finally { submit.disabled = false; submit.removeAttribute('aria-busy'); }
  });
  dialog.addEventListener('close', () => { dialog.remove(); if (opener?.isConnected) opener.focus(); });
  dialog.showModal();
  return dialog;
}
