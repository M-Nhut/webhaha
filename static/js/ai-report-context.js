/* Native context selection; a changed class must not retain another class's learner. */
(() => {
  const course = document.getElementById('ai-course');
  course?.addEventListener('change', () => {
    const student = course.form.elements.student_id;
    if (student) student.value = '';
    course.form.requestSubmit();
  });
})();
