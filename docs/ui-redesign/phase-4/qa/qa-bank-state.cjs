const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
let fetches = 0;
const context = {window: {addEventListener(){}, removeEventListener(){}, location: {reload(){}},
  renderFormulas(){}, toEditableLatex: x => x}, document: {querySelector(){return null;}, getElementById(){return null;}},
  AbortController, console, confirm: () => true, fetch: async () => {fetches++; throw new Error('Mất kết nối');}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/modules/question_bank_detail.js', 'utf8'), context);
let checks=0;
const equal=(a,b)=>{assert.equal(a,b);checks++};
(async()=>{
 const manager = context.bankQuestionsManager({questions: [{id:1, question_type:'single', can_edit:false, can_delete:false},
   {id:2, question_type:'single', can_edit:true, can_delete:true, options:[{option_text:'A',is_correct:true},{option_text:'B',is_correct:false}]},
   {id:3,question_type:'true_false',can_edit:true,can_delete:true,options:[{option_text:'a) Ý a',is_correct:true}]}], canEdit:true, csrfToken:'test'});
 manager.$nextTick=fn=>fn(); manager.$el={};
 equal(manager.canEditQuestion(manager.questions[0]),false);
 await manager.toggleOption(1,0,true);equal(fetches,0);
 await manager.toggleOption(2,1,true);
 equal(manager.questions[1].options[0].is_correct,true);equal(manager.questions[1].options[1].is_correct,false);
 equal(manager.questions[1].mutationBusy,false);equal(manager.questions[1].mutationError,true);equal(manager.questions[1].mutationStatus,'Mất kết nối');
 await manager.setTrueFalseOption(3,0,false);equal(manager.questions[2].options[0].is_correct,true);
 equal(manager.questions[2].mutationBusy,false);equal(manager.questions[2].mutationError,true);
 manager.editingId=2; manager.editingForm={...manager.questions[1], question_text:'Câu đã sửa',curriculum_mode:'general',learning_metadata:{statements:[],short_answer:{mode:'text',tolerance:'0'}}};
 manager.editReviewed=true;
 await manager.saveEdit(2);equal(manager.editingForm.question_text,'Câu đã sửa');equal(manager.editSaving,false);equal(manager.editError,'Mất kết nối');
 let resolveResponse;
 context.fetch=()=>{fetches++;return new Promise(resolve=>resolveResponse=resolve)};
 const pending1=manager.toggleOption(2,1,true);const before=fetches;
 await manager.toggleOption(2,0,true);equal(fetches,before);
 resolveResponse({ok:true,status:200,redirected:false,json:async()=>({success:true,question:{id:2,options:[{option_text:'A',is_correct:false},{option_text:'B',is_correct:true}]}})});
 await pending1;equal(manager.questions[1].options[1].is_correct,true);equal(manager.questions[1].mutationBusy,false);
 manager.questions[1].detail_url='/detail/2'; manager.questions[1].detailsLoaded=false;
 const load1=manager.loadDetails(manager.questions[1]); const count=fetches;
 const load2=manager.loadDetails(manager.questions[1]); equal(fetches,count);equal(load1,load2);
 resolveResponse({ok:false,status:403,redirected:false,json:async()=>({})}); await load1;
 equal(manager.questions[1].detailsLoading,false);equal(manager.questions[1].detailsLoaded,false);equal(manager.questions[1].detailsError.includes('quyền'),true);
 context.fetch=async()=>({ok:true,status:200,redirected:false,json:async()=>({success:true,question:{id:2,question_text:'Đã tải'}})});
 await manager.retryDetails(manager.questions[1]);equal(manager.questions[1].detailsLoaded,true);equal(manager.questions[1].detailsError,'');
 equal(manager.canEditQuestion({question_type:'essay',can_edit:true}),false);
 console.log(JSON.stringify({checks,pass:true}));
})().catch(error=>{console.error(error);process.exitCode=1});
