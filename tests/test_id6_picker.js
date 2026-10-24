/* The active picker reads file metadata; it never creates IDs or calls an API. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let requests = 0;
const sandbox = {window: {ID6_CATALOG: [
  {id: 1, grade:'9', chapter:'8', section:'i', category:'1'},
  {id: 2, grade:'9', chapter:'8', section:'i', category:'2'},
  {id: 3, grade:'9', chapter:'6', section:'4', category:'1'},
]}, fetch: async () => { requests++; throw Error('Picker must not request a generated ID'); }};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('static/js/id6_picker.js','utf8'), sandbox);
(async () => {
  const source = '9C8Ni-1D.7';
  const q = {source_id:source, curriculum_node_id:1, question_type:'single', difficulty_level:'nhan_biet', options:[{text:'answer',is_correct:true}]};
  const picker = sandbox.id6Picker(q);
  picker.init();
  await picker.changed();
  assert.equal(picker.nodes.length,2);
  assert.equal(picker.preview,'%['+source+']');
  assert.equal(q.curriculum_node_id,1);
  q.question_type='true_false'; picker.changeType();
  assert.equal(q.statements.length,4);
  assert.equal(q.options.length,0);
  q.question_type='short_answer'; picker.changeType();
  assert.equal(q.options.length,0);
  q.question_type='single'; picker.changeType();
  assert.equal(q.options[0].text,'answer');
  picker.category='2'; await picker.changed();
  assert.equal(q.curriculum_node_id,2);
  assert.equal(q.source_id,source);
  assert.equal(picker.preview,'%['+source+']');
  picker.changeChapter();
  assert.equal(picker.section,'');
  assert.equal(picker.category,'');
  assert.equal(q.curriculum_node_id,null);
  const legacy = sandbox.id6Picker({source_id:'9C6N4-1D.7',question_type:'single'});
  legacy.init();
  assert.equal(legacy.preview,'');
  const general = {curriculum_mode:'general',curriculum_node_id:1,question_category:'Đại số',question_type:'single'};
  const generalPicker = sandbox.id6Picker(general);
  generalPicker.init();
  assert.equal(general.curriculum_node_id,null);
  assert.equal(general.question_category,'Đại số');
  assert.equal(generalPicker.preview,'');
  assert.equal(requests,0);
  console.log('ID6 picker: 18 assertions passed for source identity, active catalog, answer drafts and general mode.');
})().catch(error=>{console.error(error);process.exitCode=1;});
