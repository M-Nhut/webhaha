/* Configure MathJax before the formula renderer and the local library load. */
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    processEscapes: true
  },
  options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre'] },
  startup: {
    typeset: false,
    ready() {
      MathJax.startup.defaultReady();
      MathJax.startup.promise.then(() => window.renderFormulas && window.renderFormulas(document.body));
    }
  }
};
