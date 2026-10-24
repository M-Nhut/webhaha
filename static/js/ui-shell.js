/* Shared icons, feedback, avatar fallback and accessible navigation drawer. */
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) window.lucide.createIcons();
  if (window.renderFormulas) window.renderFormulas(document.body);
  document.querySelectorAll('[data-flash-dismiss]').forEach(button => button.addEventListener('click', () => button.closest('.flash')?.remove()));
  const fallback = document.body.dataset.avatarFallback;
  document.querySelectorAll('img[data-avatar-fallback], img[src*="/static/avatars/"]').forEach(avatar => {
    const source = avatar.dataset.avatarFallback || fallback;
    if (!source) return;
    const replace = () => { if (avatar.getAttribute('src') !== source) avatar.src = source; };
    avatar.addEventListener('error', replace, {once: true});
    if (avatar.complete && avatar.naturalWidth === 0) replace();
  });
  const sidebar = document.getElementById('primary-navigation');
  const trigger = document.querySelector('[data-sidebar-toggle]');
  const content = document.querySelector('.main-area');
  const scrim = document.querySelector('.sidebar-scrim');
  if (!sidebar || !trigger || !content || !scrim) return;
  const mobile = window.matchMedia('(max-width: 1199px)');
  const navScroll = sidebar.querySelector('.nav-section');
  let opener = trigger;
  let open = false;
  const close = (restoreFocus = true) => {
    open = false;
    sidebar.classList.remove('is-open');
    sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal');
    scrim.classList.remove('is-open'); scrim.hidden = true;
    content.inert = false;
    document.body.classList.remove('nav-open');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', 'Mở điều hướng');
    if (restoreFocus && opener?.isConnected) opener.focus();
  };
  const show = () => {
    if (!mobile.matches) return;
    opener = document.activeElement;
    open = true;
    sidebar.classList.add('is-open');
    sidebar.setAttribute('role', 'dialog'); sidebar.setAttribute('aria-modal', 'true');
    scrim.hidden = false; scrim.classList.add('is-open');
    content.inert = true;
    document.body.classList.add('nav-open');
    trigger.setAttribute('aria-expanded', 'true');
    trigger.setAttribute('aria-label', 'Đóng điều hướng');
    sidebar.querySelector('[data-sidebar-close]')?.focus();
  };
  trigger.addEventListener('click', () => open ? close() : show());
  document.querySelectorAll('[data-sidebar-close]').forEach(button => button.addEventListener('click', () => close()));
  sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', () => { if (open) close(false); }));
  document.addEventListener('keydown', event => {
    if (!open) return;
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key === 'Tab') {
      const elements = [...sidebar.querySelectorAll('a[href],button:not([disabled])')].filter(el => el.getClientRects().length);
      const first = elements[0], last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });
  mobile.addEventListener('change', event => {
    const navigationHadFocus = sidebar.contains(document.activeElement) || document.activeElement === trigger;
    close(false);
    if (navigationHadFocus) {
      if (event.matches) trigger.focus();
      else (sidebar.querySelector('[aria-current="page"]') || sidebar.querySelector('.nav-item')).focus();
    }
  });
  window.addEventListener('pageshow', () => close(false));
  document.body.classList.add('has-ui-shell');
  const active = navScroll.querySelector('[aria-current="page"]');
  if (active) {
    const top = active.getBoundingClientRect().top - navScroll.getBoundingClientRect().top;
    navScroll.scrollTop += top - Math.max(0, (navScroll.clientHeight - active.offsetHeight) / 2);
  }
});
