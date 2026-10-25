/* Native context selection; a changed class must not retain another class's learner. */
/* Native context selection; a changed class must not retain another class's learner. */
(() => {
  const course = document.getElementById('ai-course');
  const student = document.getElementById('ai-person');
  course?.addEventListener('change', () => {
    const learner = course.form.elements.student_id;
    if (learner) learner.value = '';
    course.form.requestSubmit();
  });
  // Changing the learner submits too, so both selects behave the same.
  // The "Xem báo cáo" button remains as the no-JavaScript fallback.
  student?.addEventListener('change', () => {
    if (!student.disabled) student.form.requestSubmit();
  });
})();
