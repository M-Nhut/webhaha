/* Profile presentation helpers; both WTForms submissions remain native POSTs. */
document.addEventListener('DOMContentLoaded', () => {
  const avatarInput = document.querySelector('[data-profile-avatar]');
  const preview = document.getElementById('avatar-preview');
  const avatarStatus = document.querySelector('[data-profile-avatar-status]');
  let previewRequest = 0;
  let activeReader;
  const showAvatarStatus = (message, error = false) => {
    if (!avatarStatus) return;
    avatarStatus.textContent = message;
    avatarStatus.hidden = !message;
    avatarStatus.classList.toggle('is-error', error);
  };
  if (avatarInput && preview) {
    const originalSource = preview.getAttribute('src');
    avatarInput.addEventListener('change', () => {
      const request = ++previewRequest;
      if (activeReader?.readyState === FileReader.LOADING) activeReader.abort();
      const file = avatarInput.files?.[0];
      if (!file) { preview.src = originalSource; showAvatarStatus(''); return; }
      if (!/\.(jpe?g|png)$/i.test(file.name)) {
        preview.src = originalSource;
        showAvatarStatus('Không thể xem trước. Chọn ảnh JPG, JPEG hoặc PNG.', true);
        return;
      }
      showAvatarStatus('Đang đọc ảnh…');
      const reader = new FileReader();
      activeReader = reader;
      reader.addEventListener('load', () => {
        if (request !== previewRequest) return;
        preview.src = reader.result;
        showAvatarStatus(`Đã chọn ${file.name}. Lưu thông tin để cập nhật ảnh.`);
      });
      reader.addEventListener('error', () => {
        if (request !== previewRequest) return;
        preview.src = originalSource;
        showAvatarStatus('Không đọc được ảnh. Hãy chọn lại tệp.', true);
      });
      reader.readAsDataURL(file);
    });
  }
  document.querySelectorAll('.profile-page img[data-avatar-fallback]').forEach(image => {
    const fallback = image.dataset.avatarFallback;
    const useFallback = () => {
      if (image === preview && image.getAttribute('src')?.startsWith('data:')) {
        showAvatarStatus('Không hiển thị được ảnh đã chọn. Hãy chọn lại tệp ảnh.', true);
      }
      if (image.getAttribute('src') !== fallback) image.src = fallback;
    };
    image.addEventListener('error', useFallback);
    if (image.complete && image.naturalWidth === 0) useFallback();
  });
  document.querySelectorAll('[data-profile-password-toggle]').forEach(button => {
    const input = document.getElementById(button.dataset.profilePasswordToggle);
    if (!input) return;
    button.hidden = false;
    const label = document.querySelector(`label[for="${input.id}"]`)?.textContent.trim().toLocaleLowerCase('vi') || 'mật khẩu';
    button.addEventListener('click', () => {
      const reveal = input.type === 'password';
      input.type = reveal ? 'text' : 'password';
      button.textContent = reveal ? 'Ẩn' : 'Hiện';
      button.setAttribute('aria-pressed', String(reveal));
      button.setAttribute('aria-label', `${reveal ? 'Ẩn' : 'Hiện'} ${label}`);
    });
  });
  const passwordForm = document.querySelector('[data-profile-password-form]');
  if (passwordForm) {
    const newPassword = passwordForm.querySelector('[name="new_password"]');
    const confirmPassword = passwordForm.querySelector('[name="confirm_password"]');
    const matchStatus = passwordForm.querySelector('[data-profile-password-match]');
    const serverInvalid = confirmPassword?.getAttribute('aria-invalid') === 'true';
    const updateMatch = () => {
      if (!newPassword || !confirmPassword || !matchStatus) return;
      const mismatch = !!confirmPassword.value && confirmPassword.value !== newPassword.value;
      confirmPassword.setCustomValidity(mismatch ? 'Mật khẩu nhập lại chưa khớp.' : '');
      confirmPassword.setAttribute('aria-invalid', String(mismatch || serverInvalid));
      matchStatus.textContent = mismatch ? 'Mật khẩu nhập lại chưa khớp với mật khẩu mới.' : '';
      matchStatus.hidden = !mismatch;
    };
    newPassword?.addEventListener('input', updateMatch);
    confirmPassword?.addEventListener('input', updateMatch);
    passwordForm.addEventListener('submit', event => {
      updateMatch();
      if (confirmPassword && !confirmPassword.validity.valid) {
        event.preventDefault();
        confirmPassword.reportValidity();
      }
    });
  }
  const summary = document.querySelector('[data-profile-error-summary]');
  if (summary) {
    summary.focus();
    summary.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', event => {
        const target = document.getElementById(link.getAttribute('href').slice(1));
        if (!target) return;
        event.preventDefault(); target.focus(); target.scrollIntoView({block: 'center'});
      });
    });
  }
});
