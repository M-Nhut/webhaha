/* Shared curriculum selector.  ID prefixes are read-only file metadata. */
function id6Picker(question, required = false) {
  return {
    question, required, grade: '', chapter: '', section: '', category: '',
    sequence: 1, preview: '', message: '', requestVersion: 0, answerDrafts: {}, previousType: '',
    get nodes() {
      return (window.ID6_CATALOG || []).filter(n => n.grade === '9' && n.chapter === '8' && n.section === 'i');
    },
    unique(rows, key) {
      return [...new Map(rows.map(n => [n[key], n])).values()]
        .sort((a, b) => a[key].localeCompare(b[key], 'vi', {numeric: true}));
    },
    get chapters() { return this.unique(this.nodes.filter(n => n.grade === this.grade), 'chapter'); },
    get lessons() { return this.unique(this.nodes.filter(n => n.grade === this.grade && n.chapter === this.chapter), 'section'); },
    get categories() { return this.nodes.filter(n => n.grade === this.grade && n.chapter === this.chapter && n.section === this.section).sort((a,b) => Number(a.category)-Number(b.category)); },
    get selectedNode() { return this.categories.find(n => n.category === this.category); },
    init() {
      const match = (this.question.source_id || '').match(/^(9)C(8)[NHVC](i)-([1-8])[TDS](?:\.(\d+))?$/i);
      const node = this.nodes.find(n => n.id === Number(this.question.curriculum_node_id));
      this.grade = node?.grade || '9';
      this.chapter = node?.chapter || '8';
      this.section = node?.section || 'i';
      this.category = node?.category || this.question.question_category || match?.[4] || '';
      this.sequence = Number(match?.[5] || this.question.id6_sequence || 0);
      this.previousType = this.question.question_type;
      this.changed();
    },
    changeGrade() { this.chapter = ''; this.section = ''; this.category = ''; this.changed(); },
    changeChapter() { this.section = ''; this.category = ''; this.changed(); },
    changeSection() { this.category = ''; this.changed(); },
    changeType() {
      this.answerDrafts[this.previousType] = JSON.parse(JSON.stringify({options: this.question.options || [], statements: this.question.statements || []}));
      const saved = this.answerDrafts[this.question.question_type];
      if (saved) {
        this.question.options = saved.options;
        this.question.statements = saved.statements;
      } else {
        this.question.options = this.question.question_type === 'single' ? Array.from({length: 4}, (_, i) => ({text: '', option_text: '', is_correct: i === 0})) : [];
        this.question.statements = this.question.question_type === 'true_false' ? Array.from({length: 4}, (_, i) => ({id: String.fromCharCode(97+i), text: '', answer: null})) : [];
      }
      this.previousType = this.question.question_type;
      this.changed();
    },
    renderPreview() {
      const original = (this.question.source_id || '').match(/^(9)C(8)[NHVC](i)-([1-8])[TDS](?:\.(\d+))?$/i);
      if (!original) {
        this.preview = '';
        return;
      }
      this.preview = `%[${this.question.source_id}]`;
    },
    async changed() {
      if (this.question.curriculum_mode === 'general') { this.question.curriculum_node_id = null; return; }
      const version = ++this.requestVersion;
      const node = this.categories.find(n => n.category === this.category);
      this.question.curriculum_node_id = node?.id || null;
      this.message = this.question.source_id ? 'Metadata prefix chỉ đọc; số thứ tự cấp khi lưu.' : 'Cần prefix ID6 từ file; không tự sinh mã.';
      this.renderPreview();
      // Keep this async-compatible for existing Alpine callers, but never
      // call an endpoint or manufacture a prefix/sequence in the browser.
      if (version !== this.requestVersion) return;
    }
  };
}
