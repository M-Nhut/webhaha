/* Native dialogs share keyboard behavior and return focus to their opener. */
(() => {
  const openers = new WeakMap();
  const element = target => typeof target === 'string' ? document.getElementById(target) : target;
  window.AcademyDialogs = {
    open(target, opener = document.activeElement) {
      const dialog = element(target);
      if (!(dialog instanceof HTMLDialogElement) || dialog.open) return;
      openers.set(dialog, opener);
      dialog.showModal();
    },
    close(target) {
      const dialog = element(target);
      if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close();
    }
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-dialog-open]').forEach(button => button.addEventListener('click', () => window.AcademyDialogs.open(button.dataset.dialogOpen, button)));
    document.querySelectorAll('[data-dialog-close]').forEach(button => button.addEventListener('click', () => window.AcademyDialogs.close(button.closest('dialog'))));
    document.querySelectorAll('dialog[data-native-dialog]').forEach(dialog => {
      let backdropDown = false;
      const outside = event => {
        const box = dialog.getBoundingClientRect();
        return event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom);
      };
      dialog.addEventListener('pointerdown', event => { backdropDown = outside(event); });
      dialog.addEventListener('click', event => { if (backdropDown && outside(event)) dialog.close(); backdropDown = false; });
      dialog.addEventListener('close', () => {
        const opener = openers.get(dialog);
        if (opener?.isConnected) opener.focus({preventScroll: true});
        openers.delete(dialog);
      });
    });
  });
})();
