'use strict';
const $=s=>document.querySelector(s), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let csrf='', examples=[], selected=null, runId=null, timer=null, current=null, reviewSignature='', records={}, rowBindings=[], reviewSubmitting=false, querySubmitting=false, serviceFeatures=[], conditionTerms={};
let providerCatalog={},savedConnection=null,providerSettingsDirty=false,displayedConnection='',providerTouched=false;
const names={POINT:'可点识别',PARTIAL:'可确定上下界',NEEDS_INPUT:'需要补充信息',CHECK_BLOCKED:'审核未通过',REVIEW_REQUIRED:'等待研究者审核',READING_RECHECK_REQUIRED:'读取需要复核',UNSUPPORTED:'当前方法未覆盖',ADAPTER_NOT_CONNECTED:'此类问题暂未接通',NO_ADAPTER:'估计目标未接通',ESTIMATED:'估计已完成',FAILED:'本次执行未完成'};
const stageNames={PREPARING:'整理输入',READING:'读取业务',SELECT_QUERY:'选择问题',REVIEW_REQUIRED:'等待核对',READING_FACTS:'读取事实',IDENTIFYING:'计算并验证识别结果',ESTIMATING:'效应估计',RESULT:'执行结束',STOPPED:'本次分析已停止'};
const labels={query:'业务目标与研究结构',source:'事实及来源',notes:'备注与缺项',information:'总体信息来源',plan:'目标与方法计划',data:'估计数据检查',binding:'数据与研究变量对应',science:'识别条件',field_role:'字段归属',value_state:'取值与确定程度',source_coverage:'引用是否完整',assignment_outcome_independence:'完整分配与潜在结果独立',consistency:'观察结果与实际完整安排一致',finite_conditional_means:'条件均值存在且有限',network_fixed_before_treatment:'网络在处理前固定',fixed_conditioning_matches_reviewed_query:'固定背景与已确认问题一致',conditioning_is_only_fixed_pretreatment_study_background:'背景仅限固定处理前条件',node_feature_order_and_original_outcome_scale:'节点、特征顺序及原始结果尺度一致',data_population_treatment_outcome_and_fixed_context_match:'数据与目标的对象、变量和背景一致',outcome_observation_ignorable_for_estimator:'结果观测机制符合估计要求',preprocessing_and_frozen_model_applicability_reviewed:'已核对预处理和冻结模型适用范围'};
const choiceLabels={PENDING:'待核对',ACCEPTED:'确认',REJECTED:'拒绝',MATERIAL_GAP:'原材料确实缺项',READING_ERROR:'模型读取错误',NONBLOCKING_COMMENT:'不阻断的说明',DEFER_TO_MATHEMATICS:'交由数学检查',REPRESENTED:'已在事实中保留',SOURCE_STATES_MISSING:'原文明示缺失',OMITTED_ESTIMATION_NOTE:'遗漏的纯估计说明'};
Object.assign(labels,{
 selected_query_matches_native_target:'将要计算的目标，是否仍是用户提出的问题？',
 complete_model_and_constraints_preserved:'全部已有信息与限制是否完整保留？',
 method_requests_and_projections_preserved:'交给定理的对象与信息转换是否正确？',
 target_policy_population_and_weights:'政策、评价名单与权重是否对应原问？',
 network_assignment_and_variable_meaning:'网络、随机分配与变量含义是否对应材料？',
 all_information_and_restrictions_preserved:'总体信息和科学限制是否完整交接？',
 source_entailment:'原文是否支持这里采用的解释？',
 known_assignment_law:'分配规则已明确，包括联合安排的概率',
 full_vector_randomization:'完整分配向量与潜在结果独立',
 fixed_pretreatment_network:'合作网络在处理前确定并固定',
 finite_conditional_first_moments:'所需条件均值存在且有限',
 a4_source_0:'总体信息声明 1：可用范围与来源已确认',
 target_kind_and_comparison:'效应类别与比较两端保持一致',
 treatment_same_variable_and_0_1_coding_without_transformation:'数据与研究使用同一个处理变量和 0/1 编码',
 outcome_same_variable_units_scale_and_direction_without_transformation:'结果变量、单位、尺度和方向完全对应',
 context_same_fixed_pretreatment_background_without_added_selection:'固定背景对应，未增加新的筛选条件'
});
const methodNames={R1B_FULL_ASSIGNMENT:'完整分配识别',R1A_COMPOSITION:'局部效应组合识别',R2_MEAN_SUFFICIENCY:'均值充分性识别'};
async function api(path,body){const res=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});const value=await res.json();if(!res.ok)throw Error(value.error||'请求未完成');return value;}
function message(text,error=false){$('#input-message').textContent=text;$('#input-message').className='message'+(error?' error':'');}
function syncProviderOptions(h){
 const select=$('#provider'), providers=h.providers||{}, prior=select.value;
 providerCatalog=providers;savedConnection=h;
 const html=Object.entries(providers).map(([id,p])=>`<option value="${esc(id)}">${esc(p.label||p.model||id)}</option>`).join('');
 if(select.innerHTML!==html)select.innerHTML=html;
 const configured=h.configured&&providers[h.provider]?h.provider:null;
 select.value=(!providerTouched&&configured) || (providers[prior]?prior:null) || configured || Object.keys(providers)[0] || '';
}
function connectionFields(force=false){
 const id=$('#provider').value,p=providerCatalog[id]||{},h=savedConnection||{};
 const config=h.configured&&h.provider===id?{...p,...h.model_settings}:p;
 const signature=id+JSON.stringify(config);
 if(force||(!providerSettingsDirty&&displayedConnection!==signature)){
  const models=p.models||[p.model].filter(Boolean);
  $('#model-id').innerHTML=models.map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join('')+'<option value="__custom__">其他模型，自行填写…</option>';
  $('#model-id').value=models.includes(config.model)?config.model:'__custom__';
  $('#custom-model-id').value=models.includes(config.model)?'':config.model||'';
  $('#custom-model-field').hidden=$('#model-id').value!=='__custom__';
  $('#model-base-url').value=config.base_url||'';
  $('#model-workspace').value=config.workspace_id||'';
  $('#output-token-parameter').value=config.output_token_parameter||'max_tokens';
  $('#model-json-mode').value=String(config.json_mode!==false);displayedConnection=signature;
 }
 $('#provider-note').textContent=p.note||'';$('#provider-verification').textContent=p.verification||'';
 const docs=$('#provider-docs');docs.hidden=!/^https:\/\//.test(p.docs_url||'');docs.href=docs.hidden?'':p.docs_url;
 $('#workspace-field').hidden=id!=='claude';$('#custom-protocol').hidden=id!=='custom';
}
function connectionInput(){
 const id=$('#provider').value;
 return {model:($('#model-id').value==='__custom__'?$('#custom-model-id').value:$('#model-id').value).trim(),base_url:$('#model-base-url').value.trim().replace(/\/+$/,''),
  ...(id==='claude'?{workspace_id:$('#model-workspace').value.trim()}:{}),
  ...(id==='custom'?{output_token_parameter:$('#output-token-parameter').value,json_mode:$('#model-json-mode').value==='true'}:{})};
}
function connectionError(error){
 const labels={MODEL_ID_REQUIRED:'请填写所选平台已开通的模型 ID。',MODEL_BASE_URL_INVALID:'请填写 HTTPS Base URL，不含密钥、查询参数或末尾的 /chat/completions。',PROVIDER_ENDPOINT_MISMATCH:'此地址不属于所选服务。使用中转服务请选择 SUFE 或“其他 OpenAI 兼容服务”。',MODEL_WORKSPACE_INVALID:'请检查 Claude 工作空间 ID。',MODEL_SETTINGS_INVALID:'模型连接参数格式不正确。',PROVIDER_PROTOCOL_MISMATCH:'所选官方接口的协议参数不匹配。',RUN_ALREADY_BUSY:'当前任务正在运行，完成后再修改模型连接。'};
 return labels[error.message]||error.message;
}
async function health(){const h=await api('/api/health');csrf=h.csrf;serviceFeatures=h.features||[];conditionTerms=h.condition_terms||{};syncProviderOptions(h);connectionFields();$('#connection').textContent='本地服务已连接';$('#key-status').textContent=h.configured?'已保存 '+(h.providers[h.provider].label||h.provider)+' · '+(h.model_settings?.model||h.providers[h.provider].model):'尚未配置 API Key';if(!h.configured)$('#api-settings').open=true;return h;}
function claim(x){if(x===null||x===undefined)return '未提供';if(typeof x==='string')return x==='UNKNOWN'?'原文未提供／保持未知':x;if(x.value!==undefined)return x.value??x.reason??x.state;if(x.reason)return x.reason;if(x.kind&&Object.keys(x).length===1)return x.kind;return JSON.stringify(x,null,2);}
function selects(options,value,attrs=''){return `<select ${attrs}>${options.map(x=>`<option value="${esc(x)}" ${x===value?'selected':''}>${esc(choiceLabels[x]||x)}</option>`).join('')}</select>`;}
function renderExamples(){
 const card=(x,i)=>`<article class="example"><span class="tag">${esc(x.badge)}</span><h3>${esc(x.title)}</h3><p>${esc(x.description)}</p>${x.scope_note?`<p class="muted">${esc(x.scope_note)}</p>`:''}${x.citation&&/^https:\/\//.test(x.citation.url)?`<p><a href="${esc(x.citation.url)}" target="_blank" rel="noopener noreferrer">${esc(x.citation.label)}</a></p>`:''}<div class="example-actions"><button class="text-button" data-load="${i}">载入并修改 →</button><button class="text-button" data-view="${i}">${x.saved||x.saved_runs?.length?'查看历史结果':'看输入材料'}</button></div></article>`;
 const main=examples.map((x,i)=>({x,i})).filter(({x})=>x.featured!==false).sort((a,b)=>(a.x.display_order??99)-(b.x.display_order??99));
 const extra=examples.map((x,i)=>({x,i})).filter(({x})=>x.featured===false);
 $('#examples').innerHTML=main.map(({x,i})=>card(x,i)).join('')+(extra.length?`<details style="grid-column:1/-1"><summary>基础例子与缺条件追问（${extra.length} 项）</summary><p class="muted">缺条件例子用于演示追问，预期不会直接给出识别公式。历史记录不保证本次模型读取成功。</p>${extra.map(({x,i})=>card(x,i)).join('')}</details>`:'');
 $('#examples').onclick=e=>{if(e.target.dataset.load!==undefined)loadExample(examples[+e.target.dataset.load]);if(e.target.dataset.view!==undefined)showExample(examples[+e.target.dataset.view]);};
}
function exampleMaterialsHTML(x){
 const files=x.network_files;
 const fileHTML=files?'<section class="example-file-material"><h4>随示例载入的文件</h4><label><input type="checkbox" id="use-example-network" checked>使用这两份关系文件</label><p>'+files.files.map(f=>`<a href="/api/example-file?id=${encodeURIComponent(x.id)}&role=${encodeURIComponent(f.role)}" download>${esc(f.label)}（CSV）</a>`).join(' · ')+'</p><p class="muted">可用 Excel 打开。名册每行一家店；关系表每行两家相互合作的店。上传自己的对象表和关系表后，本次改用上传的文件。</p></section>':'';
 const sourceHTML=s=>{
  const optional=(x.reference_only_sources||[]).includes(s.source_id);
  const field=`<textarea rows="4" class="source-edit" aria-label="${esc(s.label||s.source_id)}">${esc(s.text)}</textarea>`;
  return `<article class="source-doc" data-source="${esc(s.source_id)}"><label><input type="checkbox" class="include-source" ${optional?'':'checked'}>${esc(s.label||s.source_id)}${optional?'（可选）':''}</label>`+
   ((x.collapsed_source_ids||[]).includes(s.source_id)?`<details class="source-table"><summary>展开完整关系表并编辑</summary>${field}</details>`:field)+'</article>';
 };
 const shown=new Set();
 const groups=(x.material_groups||[]).map(group=>{
  const sources=x.case.sources.filter(s=>group.source_ids.includes(s.source_id)&&!shown.has(s.source_id));
  sources.forEach(s=>shown.add(s.source_id));
  return sources.length?`<details class="material-group"><summary>${esc(group.title)}</summary><p class="muted">${esc(group.description)}</p>${sources.map(sourceHTML).join('')}</details>`:'';
 }).join('');
 return fileHTML+'<p class="muted">下面是这道示例的配套说明，可按实际情况修改。分析前提需要另行确认。</p>'+groups+x.case.sources.filter(s=>!shown.has(s.source_id)).map(sourceHTML).join('');
}
function loadExample(x){selected=x;$('#question').value=x.case.business_question;$('#synthetic').checked=true;$('#selected-example').hidden=false;$('#selected-example').innerHTML=`<div class="selected">已载入「${esc(x.title)}」及配套研究材料。可以修改问题，系统将重新读取。</div>`;$('#example-documents').hidden=false;$('#example-sources').innerHTML=exampleMaterialsHTML(x);if(x.network_files&&!$('#network-nodes').files.length&&!$('#network-edges').files.length){const d=x.network_files.declaration;$('#network-kind').value=d.kind;$('#network-completeness').value=d.completeness;$('#network-description').value=d.description;}message('已载入示例。点击“开始分析”后调用模型。');$('#question').focus();}
function clearInput(){selected=null;$('#question').value='';$('#documents').value='';$('#network-nodes').value='';$('#network-edges').value='';$('#network-description').value='';$('#network-kind').value='';$('#network-completeness').value='UNKNOWN';resetTableInputs();$('#file-list').innerHTML='';$('#selected-example').hidden=true;$('#example-documents').hidden=true;$('#synthetic').checked=false;message('');}
$('#question').oninput=()=>{
 if(!selected)return;
 const changed=$('#question').value.trim()!==selected.case.business_question.trim();
 $('#selected-example').innerHTML=changed
  ? '<div class="example-material-notice">问题文字已修改；配套材料仍会一起提交。若修改了对象、网络或条件，请同步核对材料。<button type="button" id="check-example-materials" class="text-button">核对配套材料 →</button></div>'
  : `<div class="selected">已载入「${esc(selected.title)}」及 ${selected.case.sources.length} 份配套说明。可以修改问题，系统将重新读取。</div>`;
 if(changed)$('#check-example-materials').onclick=()=>{$('#example-documents').open=true;$('#example-documents').scrollIntoView({behavior:'smooth',block:'start'});};
};
function literatureComparisonHTML(x){const a=x.literature_comparison;if(!a)return '';return `<details class="optional literature-comparison"><summary>改编来源与公式依据：${esc(a.label)}</summary><p>${esc(a.verdict)}</p><ul>${a.checks.map(t=>`<li>${esc(t)}</li>`).join('')}</ul><p class="muted">${esc(a.execution_boundary)}</p></details>`;}
function showExample(x){$('#saved').hidden=false;$('#saved-title').textContent=x.title;const body=x.saved_runs?.length?`<details class="optional"><summary>历史运行说明</summary><p>${esc(x.verification_note)}</p></details>`+x.saved_runs.map(r=>`<h3>${esc(r.title)}</h3>`+resultHTML(r.result,null)).join(''):x.saved?resultHTML(x.saved,null):`<p>${esc(x.case.business_question)}</p><p class="muted">${esc(x.verification_note||'该示例用于现场重新读取。')}</p>`;$('#saved-result').innerHTML=literatureComparisonHTML(x)+body;$('#saved').scrollIntoView({behavior:'smooth',block:'start'});}
async function upload(file,role){const bytes=new Uint8Array(await file.arrayBuffer());let parts=[];for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));return {name:file.name,role,content:btoa(parts.join(''))};}
$('#documents').onchange=()=>{$('#file-list').innerHTML=Array.from($('#documents').files).map(f=>`<span class="file-chip">${esc(f.name)} · ${(f.size/1024).toFixed(0)} KB</span>`).join('');};
$('#key-file').onchange=async()=>{let text=await $('#key-file').files[0]?.text();if(text!==undefined){$('#api-key').value=text.trim();text=null;$('#key-file').value='';$('#key-status').textContent='密钥已导入，请保存模型设置';}};
$('#save-key').onclick=async()=>{let key=$('#api-key').value.trim();$('#api-key').value='';try{const provider=$('#provider').value,settings=connectionInput(),savedUrl=savedConnection?.model_settings?.base_url||providerCatalog[provider]?.base_url,reuse_key=!key&&savedConnection?.configured&&savedConnection.provider===provider&&settings.base_url===savedUrl;if(!key&&!reuse_key)throw Error('请导入所选服务的 API Key，再保存连接。');await api('/api/credentials',{provider,key,reuse_key:!!reuse_key,settings});key=null;providerSettingsDirty=false;await health();$('#api-settings').open=false;message('模型连接已保存到本机内存；尚未测试账号权限，开始读取时才发出 API 请求。');}catch(e){key=null;message(connectionError(e),true);}};
$('#clear-key').onclick=async()=>{await api('/api/credentials',{provider:$('#provider').value,key:''});$('#api-key').value='';await health();};
$('#clear-input').onclick=clearInput;$('#close-saved').onclick=()=>$('#saved').hidden=true;
$('#provider').onchange=()=>{providerTouched=true;providerSettingsDirty=true;$('#api-key').value='';$('#key-file').value='';connectionFields(true);$('#key-status').textContent='已切换服务，请导入对应密钥并保存';};
for(const selector of ['#model-id','#custom-model-id','#model-base-url','#model-workspace','#output-token-parameter','#model-json-mode'])$(selector).oninput=()=>{providerSettingsDirty=true;$('#key-status').textContent='连接参数已修改，请重新保存';};
$('#model-id').onchange=()=>{$('#custom-model-field').hidden=$('#model-id').value!=='__custom__';providerSettingsDirty=true;$('#key-status').textContent='模型已修改，请保存连接设置';};
$('#start').onclick=async()=>{
 if($('#start').disabled)return;$('#start').disabled=true;
 try{providerTouched=true;if(providerSettingsDirty)throw Error('模型连接已修改，请先保存模型设置。');if(!$('#allow-send').checked)throw Error('请先确认允许将业务文字与提取材料发送给所选模型。');const h=await health();if(!h.configured)throw Error('请先配置 API Key。');if($('#provider').value!==h.provider)throw Error('所选模型与已配置密钥不对应，请先保存模型设置。');if(!serviceFeatures.includes('background_reading_review'))throw Error('后台仍是旧版本。请更新本地服务后使用自动流程；当前已保存的读取不会被删除。');if($('#question').value.trim().length<3)throw Error('请先描述业务问题。');$('#start').disabled=true;
 const uploadInput=await buildUploadInput();await checkUploadInput(uploadInput);
 const response=await api('/api/start',{question:$('#question').value,provider:$('#provider').value,...uploadInput,...inputSelection(),synthetic:$('#synthetic').checked,allow_send:true,automatic_review:true});runId=response.id;history.replaceState(null,'','#run='+runId);reviewSignature='';$('#workspace').hidden=false;$('#saved').hidden=true;$('#workspace').scrollIntoView({behavior:'smooth',block:'start'});message('已开始分析。上方输入框的后续修改不影响本次运行。');poll();
 }catch(e){message(e.message,true);}finally{$('#start').disabled=false;}
};
async function poll(){clearTimeout(timer);try{const run=await api('/api/run?id='+encodeURIComponent(runId));current=run;renderRun(run);if(run.busy)timer=setTimeout(poll,1600);}catch(e){$('#progress').textContent='连接暂时中断：'+e.message+'。3 秒后尝试获取当前任务状态，不重复调用模型。';timer=setTimeout(poll,3000);}}
function renderRun(r){
 $('#steps').hidden=!!r.automatic_review;
 $('#workspace-title').textContent=r.result?'本次分析结果':'正在分析你的问题';
 $('#run-label').textContent=(r.synthetic?'合成研究':'研究审核')+' · '+r.provider+' · '+r.id.slice(0,8);
 const last=r.events.at(-1),elapsed=Math.round((Date.now()/1000)-(last?.time||r.created));$('#progress').innerHTML=(r.busy?'<span class="spinner"></span>':'')+esc(last?.message||stageNames[r.stage])+ (r.busy?` <span class="muted">本阶段 ${elapsed} 秒</span>`:'');
 const level=r.stage==='ESTIMATING'||r.estimate||r.review_kind==='data'?3:r.stage==='IDENTIFYING'||r.result?.backend_called||r.review_kind==='science'||r.review_kind==='information'?2:r.queries.length?1:0;$('#steps').querySelectorAll('li').forEach((e,i)=>e.classList.toggle('active',i<=level));
 $('#run-error').hidden=!r.error;$('#run-error').innerHTML=r.error?`<p>${esc(errorExplanation(r.error))}</p><details><summary>技术诊断（可选）</summary><p>${esc(r.error.code+'：'+r.error.message)}</p></details>`:'';
 $('#retry-reading').hidden=!r.can_retry_reading;$('#retry-reading').disabled=r.busy;
 $('#query-select').innerHTML=r.stage==='SELECT_QUERY'?r.queries.map(q=>`<button class="secondary query-button" data-query="${esc(q.query_id)}">${esc(claim(q.business_goal||q.goal))} →</button>`).join(''):'';
 $('#query-select').onclick=async e=>{
  if(!e.target.dataset.query||querySubmitting||current?.busy)return;
  querySubmitting=true;$('#query-select').querySelectorAll('button').forEach(b=>b.disabled=true);
  try{await api('/api/action',{id:runId,action:'select',payload:{query_id:e.target.dataset.query}});await poll();}
  catch(error){$('#run-error').hidden=false;$('#run-error').textContent=error.message;}
  finally{querySubmitting=false;}
 };
 const warnings=r.attachment_report?.warnings||[];$('#material-summary').innerHTML=warnings.length?`<p class="message error">附件读取提示：${esc(warnings.join('；'))}。请检查是否需要补充文字材料。</p>`:'';
 const signature=r.id+'|'+r.review_kind+'|'+Object.values(r.review_sheets||{}).map(x=>x.binding_sha256).join('|');
 if(r.review_kind&&signature!==reviewSignature){reviewSignature=signature;renderReview(r);}
 else if(r.review_kind)renderCompactReview(r);
 $('#review').hidden=!r.review_kind||r.busy||(r.automatic_review&&!['science','data','information'].includes(r.review_kind));$('#submit-review').disabled=r.busy;
 renderClarification(r);
 const goal=r.queries.find(q=>q.query_id===r.query_id)?.business_goal;
 $('#result').innerHTML=r.result?`${goal?`<p class="answer-goal"><b>你提出的问题</b><br>${esc(claim(goal))}</p>`:''}${r.automatic_review?`<p class="muted">${r.result.independent_replay?'问题已核对。以下结论依赖所列假设。':'本次尚未得到通过验证的识别结果。'}</p>`:''}`+resultHTML(r.result,null):'';
 $('#events').innerHTML=r.events.map(e=>`<li>${new Date(e.time*1000).toLocaleTimeString()} · ${esc(e.message)}</li>`).join('');
 $('#downloads').innerHTML=`<details class="optional"><summary>下载输入与结果</summary><div class="download-links">${r.downloads.map(n=>`<a href="/api/download?id=${encodeURIComponent(r.id)}&name=${encodeURIComponent(n)}">${esc(n)}.json ↓</a>`).join('')}</div></details>`;
}
$('#retry-reading').onclick=async()=>{
 try{$('#retry-reading').disabled=true;await api('/api/action',{id:runId,action:'retry_reading',payload:{}});await poll();}
 catch(e){$('#run-error').textContent=e.message;}
 finally{$('#retry-reading').disabled=!!current?.busy;}
};
function clarificationText(item,result){
 const raw=typeof item==='string'?item:item.display_question||item.question||item.text||'请说明下面这段原文的意思；不清楚时可以直接注明。';
 const copies={"请说明理论识别可以使用的总体观测信息及覆盖范围；有限样本不能代替。": "除了这一次收集的记录，你还有其他可用资料吗？例如以往试验的记录，或研究方案已经给出的平均结果、发生比例。请说明资料来自哪里、包括哪些对象，以及他们接受了什么处理。只有这一次的记录，或暂时不清楚，也请直接说明；系统会检查这些资料能用于哪一步。", "请核对并补充完整历史分配规则及其参数；规则资料不完整不等于当前数学方法未覆盖。": "当时是怎样决定谁接受处理、谁不接受的？如果抽签，请说明每人中签的机会，或各组抽多少人；如果不是抽签，请说明实际选择办法。可以直接上传试验方案。", "请说明原试点是否逐对象独立抽签，以及每个对象的已知概率。": "当时是每个对象分别抽签，还是先规定一共选多少个？如果分别抽签，每个对象中签的机会是多少？例如“每家各自抽签，各有一半机会”；没有记录时请说明。", "请明确比较两端的自身处理、同伴状态及相减方向。": "你想比较哪两种情形？请分别说明本人做什么、相关的人或单位做什么，以及想知道哪一种比另一种增加或减少多少。", "请明确评价全体、指定子集还是单个对象，以及汇总方式。": "你关心全部对象、其中一组，还是某一个对象？如果有多个对象，是看每个对象的结果，还是平均结果？如果取平均，每个对象是否同等重要？", "请明确同伴分组定义；不能仅凭受到同事影响而选择分组规则。": "你想怎样描述相关对象的参与情况？例如参与的人数、参与比例，或是否有人参与。请说明你的分法；还没决定时可以直接注明。", "请核对原文是否明确：处理前固定网络。": "这些联系是在实施处理前就确定的吗？实施处理后，哪些人或单位彼此相连会不会改变？", "请核对原文是否明确：两端结果定义、期间和背景相同。": "两种情形是否比较同一个指标、同一段时间和同样的背景？如果有不同，请说明具体哪里不同。", "本问希望在哪些已指定的条件下评价，还是希望跨背景评价？请说明条件、所指背景及时间；尚未决定可以保留。": "这个问题只看某个地区、时期或条件下的效果，还是把不同情况合在一起看？请说明你关心的范围；还没决定可以直接说。", "本次评价的是处理前研究名单中的全体／事先确定的小组，还是按本轮实际启用、回访或结果筛选出的对象？请说明选择依据；不需要提供提出问题的日期。": "这次想评价哪些对象，是怎样选出来的？是试点前名单中的全部或事先选好的一组，还是试点后按是否使用、是否回访或实际表现选出的？不需要说明你何时提出问题。", "关注的结果是二元状态、次数，还是连续数值？请说明结果的取值含义。": "这个结果记录的是什么？例如是否感染（是/否）、投诉次数，或收入金额。若用数字编码，请说明每个值的含义。", "请核对效应名称、两端条件和相减方向；系统不会交换两端或补齐基准。": "你想知道哪种情形比哪种情形增加或减少多少？请分别写明本人和相关对象在两种情形下做什么。", "请核对要用哪个完整方案减去哪个基准方案，以及是否比较同一结果、单位、期间与研究背景。": "你希望用哪个方案与哪个方案比较？请写明各方案中谁接受处理、谁不接受，以及比较的是不是同一批对象、同一指标、同一时期和同一背景。", "下面这些说明是在描述已有资料与待确认事项，还是希望为本次计算另外增加条件？请说明你的原意。": "这段话是在介绍已有资料，还是你希望本次分析采用的一项假设？如果只是可能采用、还没有决定，或明确不采用，请直接说明。"};
 if(Object.hasOwn(copies,raw))return copies[raw];
 const match=raw.match(/^本次计算需要以下条件，请说明是否采用：“(.+)”。不知道或尚未决定也可以说明。$/);
 if(match){
  const science={"给定本次背景，完整处理安排与潜在结果独立": "在本次限定的背景下，处理名单不因对象在不同安排下可能出现的结果而被选择。", "实际观察结果对应实际完整安排下的潜在结果": "实际记录的结果对应当时实际执行的安排，包括本人和其他对象接受的处理。", "本次所需的总体条件均值存在且有限": "本次比较用到的平均结果有定义，而且不是无穷大。", "最终完整处理名单相同时，第一阶段配额方案不再直接影响结果": "只要最终每个对象接受的处理相同，最初抽到哪一种名额方案就不会另外改变结果。"};
  const known=Object.values(conditionTerms).find(x=>x.text===match[1]);
  const meaning=science[match[1]]||known?.explanation?.meaning;
  if(meaning)return '本方法需要采用这项假设：'+meaning+' 本次是否采用？可以回答“采用”“不采用”或“尚未决定”，并说明依据；系统不会默认采用。';
 }
 return raw;
}
function renderClarification(r){
 const items=(r.user_question?.items||[]).map(x=>clarificationText(x,r.result));
 if(r.automatic_review&&r.review_kind==='notes')items.push(...Object.values(r.review_sheets?.notes?.notes||{}).map(n=>'下面这句话是背景介绍，还是本次要采用的假设？也可以回答不采用或尚未决定：'+n.text));
 if(r.result?.state==='NEEDS_INPUT')items.push(...(r.result.clarification_questions||[]).map(x=>clarificationText(x,r.result)));
 $('#clarification').hidden=r.busy||!items.length;
 const quotes=[...new Set((r.user_question?.items||[]).flatMap(x=>x.source_texts||[]))];
 $('#clarification-questions').innerHTML=(r.user_question?.message?`<p>${esc(r.user_question.message)}</p>`:'')+'<ul>'+[...new Set(items)].map(q=>`<li>${esc(q)}</li>`).join('')+'</ul>'+ (quotes.length?`<div class="clarification-source"><b>需要说明的原文</b>${quotes.map(q=>`<blockquote>${esc(q)}</blockquote>`).join('')}</div>`:'')+'<p class="muted">提交后重新检查。暂时无法补充时，可保留当前结果，之后再继续。</p>';
 $('#send-clarification').disabled=r.busy;
}
function errorExplanation(error){
 const text=error.code+' '+error.message;
 if(error.code==='READING_REVIEW_DISAGREEMENT')return '模型对原文的理解仍有冲突，识别尚未开始。可点击“重新核对”；无需改写已明确的条件。';
 if(error.code==='INCOMPLETE_COMPLETION')return '模型回复被截断，核对未完成。请点击“重新核对”；无需修改研究问题。';
 if(/API_KEY|401|403|Unauthorized/.test(text))return '模型连接失败，请检查 API Key 和模型权限。已提交的材料仍保留。';
 if(/TIMEOUT|timeout|timed out/i.test(text))return '模型请求超时。此前的读取已保存，可点击“重新核对”继续。';
 if(/LIMIT|429/.test(text))return '已达到调用次数上限，或模型服务正在限流。请检查额度和服务状态后重试。';
 if(/READING_AUDIT/.test(text))return '模型的核对回复格式不正确，识别尚未开始。材料已保存，可重新核对。';
 return '本次运行未完成，输入和读取记录已保存。请展开技术诊断查看错误。';
}
$('#send-clarification').onclick=async()=>{
 const text=$('#clarification-answer').value.trim();
 if(text.length<3){$('#clarification-message').textContent='请先填写补充说明。';return;}
 try{
  $('#send-clarification').disabled=true;
  await api('/api/action',{id:runId,action:'clarify',payload:{text}});
  $('#clarification-answer').value='';$('#clarification-message').textContent='';await poll();
 }catch(e){$('#clarification-message').textContent=e.message;}
 finally{$('#send-clarification').disabled=!!current?.busy;}
};
function rowTitle(path,field){return labels[path]||field?.definition?.meaning||field?.role||path||'核对本问材料是否完整保留';}
function sourceText(v){return typeof v==='string'?v:v.quote||v.text||JSON.stringify(v);}
function compactChanges(r){
 const changes=Object.values(r.review_sheets||{}).flatMap(s=>Object.values(s.changes||{}));
 return {changes,allowed:r.review_kind==='changes'&&changes.length>0&&changes.length<=12&&changes.every(d=>
  /^\/(additional_restrictions|unresolved)(\/|$)/.test(d.field_path)||(/\/source_ids(\/|$)/.test(d.field_path)&&JSON.stringify(d).length<2500))};
}
function fieldName(path){
 if(path.startsWith('/additional_restrictions'))return '模型列出的额外说明';
 if(path.startsWith('/unresolved'))return '模型列出的待解决问题';
 const names={'/study':'研究对象与变量','/target/first':'比较的第一种情形','/target/second':'比较的第二种情形','/target':'比较目标与评价对象','/assignment':'试点分配安排','/information':'可用信息','/scientific_statements':'拟采用的科学条件'};
 return Object.entries(names).find(([key])=>path.startsWith(key))?.[1]||'材料记录';
}
function noteItems(r){
 if(r.recheck_preview?.items?.length)return r.recheck_preview.items;
 const sheet=r.review_sheets?.source, facts=sheet?.fields?.['']?.candidate||r.plan?.reading_candidate||{};
 return ['additional_restrictions','unresolved'].flatMap(name=>(facts[name]||[]).map((item,i)=>({path:`/${name}/${i}`,text:typeof item==='string'?item:item.text,
  quotes:(item.source_ids||[]).filter(sid=>sheet?.source_catalog?.[sid]).map(sid=>sourceText(sheet.source_catalog[sid]))})));
}
function renderIssues(r){
 const items=noteItems(r),delta=compactChanges(r),box=$('#review-issues');
 const value=x=>x==null?'未列出':Array.isArray(x)?(x.length?x.map(v=>typeof v==='object'?(v.text||JSON.stringify(v)):v).join('；'):'无此项'):typeof x==='object'?(x.text||JSON.stringify(x)):String(x);
 box.hidden=!items.length&&!delta.changes.length;
 box.innerHTML=delta.changes.length?`<h4>复核具体改了什么</h4><p>以下是模型修改的内容，请对照原文核对。采用哪些研究假设会另行确认。</p>${delta.changes.map(d=>`<article class="issue-item"><b>${esc(fieldName(d.field_path))}${d.field_path.includes('/source_ids')?' · 原文引用':''}</b><p>复核前：${esc(value(d.before))}</p><p>复核后：${esc(value(d.after))}</p></article>`).join('')}${delta.allowed?'':'<p>本次还改动了目标或其他关键事实，需要核对完整变化，不能一键接受。</p>'}`:
  items.length?`<h4>模型标记了 ${items.length} 条需要核对的说明</h4><p>这些说明需要重新核对，未必是材料缺失。可点击下方按钮让模型检查原文。</p>${items.map(item=>`<article class="issue-item"><p>${esc(item.text)}</p>${item.quotes?.length?`<details><summary>查看对应原文</summary>${item.quotes.map(q=>`<blockquote>${esc(q)}</blockquote>`).join('')}</details>`:''}</article>`).join('')}`:'';
 const show=items.length>0&&!delta.allowed&&['source','notes','changes'].includes(r.review_kind);
 $('#request-recheck').hidden=!show;
 $('#request-recheck').disabled=!r.recheck_preview?.available||r.busy||reviewSubmitting;
 $('#request-recheck').textContent='让模型复核这 '+items.length+' 条说明';
 if(show&&!r.recheck_preview){box.innerHTML+='<p class="message">当前服务版本不支持自动复核，请更新后继续。本次读取已保存。</p>';}
 else if(show&&!r.recheck_preview.available)box.innerHTML+='<p>自动复核暂不能继续：未找到对应原文，或已达到复核次数上限。请查看详细记录。</p>';
 if(show)$('#confirm-summary').hidden=true;
}
// Presentation compatibility for a running server that predates review_summary.
// Read existing candidates only: do not repair model answers or grant a review.
function reviewSummary(r){
 const sheets=r.review_sheets||{},templates=r.review_templates||{},plan=r.plan||{};
 const registered=registeredReviewSummary(r);
 if(registered)return registered;
 const query=(r.queries||[]).find(q=>q.query_id===r.query_id)||{},sem=query.semantics||{};
 const fields=sheets.query?.fields||{},qfield=key=>fields[`queries.${r.query_id}.${key}`]?.candidate;
 const text=x=>x===undefined||x===null?'未明确':String(claim(x));
 const candidate=sheets.source?.fields?.['']?.candidate||plan.reading_candidate;
 const facts=candidate&&typeof candidate==='object'?candidate:{},target=facts.target||{};
 let comparison=text(query.business_goal||qfield('goal'));
 if(target.kind==='FIXED_POLICY_MEAN'&&target.assignment&&typeof target.assignment==='object'){
  const pairs=Object.entries(target.assignment);
  comparison=[1,0].map(level=>{const nodes=pairs.filter(([,v])=>v===level).map(([n])=>n);return nodes.length?
   (pairs.length<=6?nodes.join('、'):nodes.length+' 个对象')+(level?'接受处理':'不接受处理'):null;}).filter(Boolean).join('；')||comparison;
 }
 if([target.first,target.second].every(end=>end&&typeof end==='object'&&'own' in end)){
  const arm=end=>{
   const own={0:'本人不接受处理',1:'本人接受处理'}[end.own]||'本人状态待明确';
   const peer=facts.exposure?.kind==='STRICT_MAJORITY_TIES_LOW'
    ?({0:'相邻对象中至多一半接受处理',1:'相邻对象中超过一半接受处理'}[end.exposure]||'同伴状态待明确')
    :'同伴状态 '+text(end.exposure);
   return own+'、'+peer;
  };
  comparison=arm(target.first)+'，减去'+arm(target.second);
 }
 const contrastFacts=facts.version==='network-policy-contrast-reading-1'&&target.kind==='FIXED_POLICY_MEAN_DIFFERENCE';
 if(contrastFacts&&target.first?.assignment&&target.second?.assignment)comparison='第一方案：'+policyText(target.first.assignment)+'；减去第二方案：'+policyText(target.second.assignment);
 const commonTarget=contrastFacts?(target.first||{}):target;
 const scope=Array.isArray(commonTarget.population)?`${commonTarget.population.length} 个评价对象`:text(sem.target_population||qfield('semantics.target_population'));
 const aggregation=commonTarget.aggregation==='EQUAL_MEAN'?'等权平均':text(sem.aggregation||qfield('semantics.aggregation'));
 const outcome=text(facts.study?.outcome||sem.outcome||qfield('semantics.outcome')||fields['common.outcome']?.candidate);
 const conditions=[],assignment=facts.assignment||{},statements=facts.scientific_statements||{};
 const scienceNames={assignment_outcome_independence:'完整安排与潜在结果独立',consistency:'实际结果对应实际完整安排',finite_conditional_means:'所需平均值存在且有限'};
 if(assignment.kind==='INDEPENDENT_BERNOULLI'){
  const probabilities=[...new Set(Object.values(assignment.probabilities||{}).map(String))];
  conditions.push('每个对象独立随机分配'+(probabilities.length===1?'，启用概率为 '+probabilities[0]:'，各对象的概率见方案'));
 }else if(assignment.kind)conditions.push('按材料中的分配方案：'+assignment.kind);
 else if(fields['common.assignment_law']?.candidate)conditions.push(text(fields['common.assignment_law'].candidate));
 const proposed=[],adopted=[];
 for(const [key,item] of Object.entries(statements)){
  if(item.status==='PROPOSED')proposed.push(scienceNames[key]||key);
  else if(item.status==='ADOPTED')adopted.push(scienceNames[key]||key);
  else conditions.push((scienceNames[key]||key)+'：'+({NOT_STATED:'原文未声明',UNDECIDED:'尚未决定',NOT_ADOPTED:'不采用',REJECTED:'不采用',CONFLICTING:'材料存在冲突'}[item.status]||'状态待核对'));
 }
 if(proposed.length)conditions.push('本次拟采用：'+proposed.join('；'));
 if(adopted.length)conditions.push('原文明确采用：'+adopted.join('；'));
 const stageStatus=facts.first_stage_exclusion?.status;
 if(assignment.kind==='TWO_STAGE_QUOTA_MIXTURE')conditions.push('第一阶段条件：最终完整名单相同时，名额方案本身不再直接影响结果（'+({ADOPTED:'原文采用',PROPOSED:'拟采用'}[stageStatus]||'尚未明确采用')+'）');
 if(facts.design_facts?.network_fixed_before_treatment?.value===true)conditions.push('使用试点前固定的关系网络');
 if(!conditions.length)conditions.push('依据原研究方案；具体科学条件尚待读取，不在此默认批准。');
 const data=r.attachment_report?.factual_data;
 let dataText=data?`${data.nodes??'未知'} 个对象，${data.observed??'未知'} 条结果记录，${data.features??'未知'} 项特征。`:'以本次材料声明的总体信息为准。';
 dataText+=(facts.information||[]).some(x=>x.availability==='SYMBOLIC_POPULATION_OPERATOR')?'识别依据材料另行声明的总体信息；有限记录仅用于估计。':data?'有限记录不自动变为已知总体信息。':'';
 if((facts.information||[]).some(x=>x.operator==='ALL_OUTCOMES_TOGETHER_WITH_FULL_ASSIGNMENT'&&x.availability==='SYMBOLIC_POPULATION_OPERATOR'))dataText+=' 本次声明可用：全体对象的结果与完整使用安排的联合总体分布（符号形式）。';
 const fallbackCards=[{title:'要比较什么',lines:[comparison,scope+' · '+aggregation,outcome]},
  {title:'按什么条件计算',lines:conditions},{title:'用什么数据估计',lines:[dataText]}];
 const supplied=r.review_summary;
 const valid=supplied&&Array.isArray(supplied.cards)&&supplied.cards.length===3&&supplied.cards.every(c=>
  c&&typeof c.title==='string'&&Array.isArray(c.lines)&&c.lines.length&&c.lines.every(line=>typeof line==='string'))&&typeof supplied.compact_confirmation_available==='boolean';
 const attention=[...(plan.rejected_fields||[])];
 if(Array.isArray(supplied?.needs_individual_attention))attention.push(...supplied.needs_individual_attention);
 if(supplied?.compact_confirmation_available===false&&!attention.length)attention.push('本阶段有待处理事项，可按需展开详情；不能集中确认。');
 const changeInfo=compactChanges(r);
 if(!['query','source','science','data'].includes(r.review_kind)&&!changeInfo.allowed)attention.push('本阶段需要先处理材料中的具体问题。');
 const entries=Object.entries(templates);
 if(!entries.length||Object.keys(sheets).length!==entries.length)attention.push('审核记录未完整返回，请刷新状态后重试。');
 for(const [name,record] of entries){
  const sheet=sheets[name];
  if(!sheet||!record.binding_sha256||record.binding_sha256!==sheet.binding_sha256)attention.push('审核记录与当前材料不对应，请刷新状态。');
  if(record.material_decisions||!record.decisions||!Object.keys(record.decisions).length)attention.push('存在需要单独判断的材料，不能集中确认。');
  for(const decision of Object.values(record.decisions||{})){
   const object=decision&&typeof decision==='object';
   const change=changeInfo.allowed&&sheet?.changes&&object&&'disposition' in decision;
   if(object&&!change&&!['field_role','value_state','source_coverage'].every(k=>k in decision))attention.push('审核记录类型需要单独处理。');
   const states=object?(change?[decision.disposition]:[decision.field_role,decision.value_state,decision.source_coverage]):[decision];
   if(states.includes('REJECTED'))attention.push('已有拒绝项，集中确认不会覆盖它。');
   else if(states.some(s=>!['PENDING','ACCEPTED'].includes(s)))attention.push('存在未支持的审核状态。');
   if(object&&!Object.keys(sheet?.source_catalog||{}).length)attention.push('缺少可核对的原材料来源。');
  }
 }
 if(facts.additional_restrictions?.length||facts.unresolved?.length)attention.push('模型标出了需要核对的说明，具体内容及处理入口见下方。');
 const localFacts=facts.version==='network-randomized-effect-reading-1';
 const fixedFacts=facts.version==='network-source-selections-1'&&target.kind==='FIXED_POLICY_MEAN';
 if(contrastFacts&&(target.operation!=='FIRST_MINUS_SECOND'||JSON.stringify(target.first?.population)!==JSON.stringify(target.second?.population)||target.first?.aggregation!==target.second?.aggregation||target.shared_outcome_and_context?.value!==true))attention.push('比较方向、共同评价名单、加权方式或共同结果背景尚未对齐。');
 if(['source','science','data'].includes(r.review_kind)&&!localFacts&&!fixedFacts&&!contrastFacts)attention.push('当前材料不足以生成可确认的条件摘要。');
 if(r.review_kind==='science'){
  if(!plan.methods?.length||plan.methods.some(m=>!(localFacts&&m.method==='R1A_COMPOSITION')&&!(fixedFacts&&m.method==='R1B_FULL_ASSIGNMENT')&&!(contrastFacts&&m.method==='R1B_ENDPOINT_DIFFERENCE')))attention.push('本路线的科学条件需要单独核对。');
  if(assignment.kind==='TWO_STAGE_QUOTA_MIXTURE'&&!['ADOPTED','PROPOSED'].includes(stageStatus))attention.push('第一阶段名额方案的排除条件尚未明确采用，不能直接确认。');
  for(const key of Object.keys(scienceNames))if(!['ADOPTED','PROPOSED'].includes(statements[key]?.status))attention.push(scienceNames[key]+'尚未明确采用或拟采用，不能直接确认。');
 }
 const cards=structuredClone(valid?supplied.cards:fallbackCards);
 if(r.review_kind==='data')cards[2].lines.push('本次确认：数据与目标对应，结果记录的缺失方式和预处理符合当前估计器要求。');
 return {cards,compact_confirmation_available:attention.length===0&&(!valid||supplied.compact_confirmation_available),
  needs_individual_attention:[...new Set(attention)],is_approval:false,
  confirmation_label:valid&&typeof supplied.confirmation_label==='string'?supplied.confirmation_label:
   r.review_kind==='changes'?'确认上述复核变化并继续':r.review_kind==='science'?'确认采用上述条件并继续':r.review_kind==='data'?'确认数据与问题对应并估计':'与原材料一致，继续'};
}
// A checked plan owns its native review identities, including DAG protocols.
// Fail closed on stale summaries, omitted worksheets, changed keys or refusals.
function reviewIdentity(sheet){const keys=sheet&&'binding_sha256' in sheet?['version','binding_sha256']:['version','bundle_sha256','candidate_sha256','problem_sha256'];return Object.fromEntries(Object.entries(sheet||{}).filter(([k])=>keys.includes(k)).sort(([a],[b])=>a.localeCompare(b)));}
function registeredReviewSummary(r){
 const s=r.review_summary;
 if(r.review_kind!=='science'||s?.contract!=='registered-web-review-1')return null;
 const errors=[...(s.needs_individual_attention||[])],plan=r.plan||{},sheets=r.review_sheets||{},records=r.review_templates||{};
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 if(!s.plan_sha256||s.plan_sha256!==plan.plan_sha256||plan.state!=='REVIEW_REQUIRED')errors.push('研究条件已变更，请刷新后重新确认。');
 if(!same(s.methods,(plan.methods||[]).map(m=>m.method)))errors.push('当前方法与确认摘要不对应。');
 if(!same(Object.keys(sheets).sort(),Object.keys(records).sort())||!same(Object.keys(sheets).sort(),Object.keys(s.review_bindings||{}).sort())||!Object.keys(sheets).length)errors.push('审核记录不完整。');
 for(const [name,sheet] of Object.entries(sheets)){
  const record=records[name],bound=s.review_bindings?.[name];
  if(!record||!bound||!same(reviewIdentity(record),reviewIdentity(sheet))||!same(reviewIdentity(bound.identity),reviewIdentity(sheet))||!same(Object.keys(record.decisions||{}).sort(),bound.decisions)||!same(Object.keys(sheet.decisions||{}).sort(),bound.decisions))errors.push('审核记录与当前材料不对应。');
  if(!Object.keys(record?.decisions||{}).length||Object.values(record?.decisions||{}).some(v=>!['PENDING','ACCEPTED'].includes(v)))errors.push('存在拒绝或尚不能确认的记录。');
 }
 const validCards=Array.isArray(s.cards)&&s.cards.length===3&&s.cards.every(c=>typeof c.title==='string'&&Array.isArray(c.lines)&&c.lines.length&&c.lines.every(x=>typeof x==='string'));
 if(!validCards)errors.push('必要条件摘要未完整返回。');
 return {...s,cards:validCards?s.cards:[{title:'当前摘要尚未完成',lines:['请保留材料，待处理当前接口问题。']}],
  compact_confirmation_available:!!s.compact_confirmation_available&&!errors.length,needs_individual_attention:[...new Set(errors)]};
}
const informationChoices={};
function informationDocuments(r){
 if(r.review_kind!=='information')throw Error('当前不是信息来源确认阶段。');
 return Object.entries(r.review_sheets||{}).map(([name,sheet])=>{
  const record=r.review_templates?.[name];
  if(!record||!['network-information-evidence-review-1','network-contrast-information-evidence-review-1'].includes(sheet.version)||JSON.stringify(reviewIdentity(record))!==JSON.stringify(reviewIdentity(sheet))||record.disposition==='REJECTED')throw Error('来源记录已变更或已拒绝，不能集中确认。');
  const docs={};for(const [ref,source] of Object.entries(sheet.source_catalog||{})){
   if(!source.doc_id)throw Error('来源材料缺少文件标识。');
   (docs[source.doc_id]??=[]).push({ref,text:sourceText(source)});
  }
  if(Object.keys(docs).length<2)throw Error('来源目录不完整。');
  return {name,sheet,docs,key:r.id+':'+sheet.binding_sha256};
 });
}
function informationRecords(r,choices){
 const groups=informationDocuments(r);if(!groups.length)throw Error('缺少来源记录。');
 const answer=structuredClone(r.review_templates);
 for(const {name,sheet,docs,key} of groups){
  const selected=choices[key];if(!docs[selected])throw Error('请先选择真正提供全部总体数值的文件。');
  const table=docs[selected].map(x=>x.ref),support=Object.entries(docs).filter(([id])=>id!==selected).flatMap(([,rows])=>rows.map(x=>x.ref));
  if(sheet.entry_source_ids&&Object.values(sheet.entry_source_ids).some(ids=>!ids.some(id=>table.includes(id))))throw Error('并非每一条总体信息都引用了这份表，请核对材料。');
  Object.assign(answer[name],{reviewer:'Local browser user',evidence:'我核对了本页原文：全部精确总体数值来自所选文件，其余引用仅解释定义，不增加信息或科学限制。',disposition:'ACCEPTED',table_source_ids:table,supporting_source_ids:support});
 }
 return answer;
}
function renderInformationQuestion(r){
 try{
  const groups=informationDocuments(r);
  $('#compact-review').innerHTML='<p>模型同时引用了信息表和说明文件。请确认：全部精确总体数值来自哪一份文件？其他文件只能解释对象、编码或期间，不能包含另一份数据、方程或限制。</p>'+groups.map((g,i)=>`<label>提供总体数值的文件<select data-information-choice="${i}"><option value="">请选择；无法确认时不要继续</option>${Object.entries(g.docs).map(([id])=>`<option value="${esc(id)}" ${informationChoices[g.key]===id?'selected':''}>${esc(id)}</option>`).join('')}</select></label>${Object.entries(g.docs).map(([id,rows])=>`<details><summary>查看 ${esc(id)} 的相关原文</summary><div class="sources">${rows.map(x=>esc(x.text)).join('\n\n')}</div></details>`).join('')}`).join('');
  const update=()=>{try{informationRecords(r,informationChoices);$('#confirm-summary').disabled=r.busy||reviewSubmitting;$('#review-message').textContent='';}catch(e){$('#confirm-summary').disabled=true;$('#review-message').textContent=e.message;}};
  $('#compact-review').querySelectorAll('[data-information-choice]').forEach(el=>{el.onchange=()=>{informationChoices[groups[Number(el.dataset.informationChoice)].key]=el.value;update();};});
  $('#compact-review').hidden=false;$('#confirm-summary').hidden=false;$('#confirm-summary').textContent='确认来源分工并继续';update();
 }catch(e){$('#compact-review').textContent=e.message;$('#confirm-summary').disabled=true;}
}
function conditionEntry(text){
 const exact=Object.values(conditionTerms).find(item=>item.text&&item.text===text);
 return exact?{...exact,text}:{text,label:text,term:'',category:'other'};
}
function conditionExplanation(item){
 const known=item.key?conditionTerms[item.key]:Object.values(conditionTerms).find(x=>x.text&&x.text===item.text);
 return known?.explanation||null;
}
function conditionHeading(item){const help=conditionExplanation(item);return esc(help?.label||item.label||item.text)+(item.term?` <span class="condition-heading-term">(${esc(item.term)})</span>`:'');}
function conditionDetailHTML(item){
 const help=conditionExplanation(item);
 return `<b>${conditionHeading(item)}</b>`+(help?
  `<p>${esc(help.meaning)}</p><p><b>${item.category==='science'?'为什么需要：':'用于：'}</b>${esc(help.purpose)}</p><details class="condition-formal"><summary>本次记录的正式条件</summary><p>${esc(item.text||item.label)}</p></details>`:
  `<p>${esc(item.text||item.label)}</p><p class="muted">此项暂无简明解释，保留本次记录的原文。</p>`);
}

function conciseReviewHTML(compact,r){
 const cards=compact.cards||[],science=r.review_kind==='science';
 const items=compact.condition_items?.length?compact.condition_items:(cards[1]?.lines||[]).map(conditionEntry);
 const scienceItems=items.filter(item=>item.category==='science');
 const headings=[...new Set((scienceItems.length?scienceItems:items).map(item=>conditionExplanation(item)?.label||item.label||item.text))];
 const info=compact.information_brief||cards[2]?.lines||[];
 const rows=[{title:'① 研究目标',status:science?'已读取 · 可核对':'请核对',lines:cards[0]?.lines?.slice(0,3)||[]},
  {title:'② 研究假设',status:science?'需你确认采用':'待核对',lines:headings},
  {title:'③ 可用信息',status:science?'已读取 · 可核对':'请核对',lines:info.slice(0,3)}];
 const open=$('#confirmation-scope')?.open?' open':'';
 return `<div class="review-highlights">${rows.map((c,i)=>`<article><div class="confirm-card-head"><h4>${esc(c.title)}</h4><span class="confirm-status ${science&&i===1?'needs-decision':''}">${esc(c.status)}</span></div>${i===1?'<ul class="condition-chips">'+c.lines.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':c.lines.map(x=>`<p>${esc(x)}</p>`).join('')}</article>`).join('')}</div>`+
  `<p class="confirmation-intent">${science?'请确认采用第②栏的假设，并核对第①、③栏。完整说明可展开查看。':'请核对下面三项是否符合原意。'}</p>`+
  `<details id="confirmation-scope" class="optional"${open}><summary>查看完整条件与适用范围（${cards.reduce((n,c)=>n+c.lines.length,0)}项说明）</summary>${cards.map((c,i)=>`<h4>${esc(rows[i]?.title||c.title)}</h4><ul>${c.lines.map((line,j)=>`<li>${i===1&&items[j]?conditionDetailHTML(items[j]):esc(line)}</li>`).join('')}</ul>`).join('')}</details>`;
}
function renderCompactReview(r){
 if(r.review_kind==='information'){renderInformationQuestion(r);return;}
 const compact=reviewSummary(r);
 $('#compact-review').innerHTML=conciseReviewHTML(compact,r);
 $('#compact-review').hidden=false;
 $('#confirm-summary').hidden=false;
 $('#confirm-summary').disabled=!compact.compact_confirmation_available||r.busy||reviewSubmitting;
 $('#confirm-summary').textContent=compact.compact_confirmation_available?compact.confirmation_label:'需先处理上述问题';
 $('#review-message').textContent=compact.needs_individual_attention.length?compact.needs_individual_attention.slice(0,2).join('；'):'';
 renderIssues(r);
}
function renderReview(r){
 records=structuredClone(r.review_templates||{});rowBindings=[];$('#use-review-json').checked=false;
 renderCompactReview(r);
 $('#review-details').open=false;
 $('#review-title').textContent={query:'系统理解的问题',source:'系统读到的研究方案',notes:'需要核对这几条说明',changes:'模型复核后改了哪些内容？',information:'这些总体信息是否确实可用？',science:'请确认本次采用的假设',data:'这些数据能否用于本次估计？'}[r.review_kind]||'请核对当前问题';
 let html='';
 if(r.plan?.proposed_target){const t=r.plan.proposed_target;html+=`<div class="target-preview"><h4>本次交给识别库的目标</h4><p>${esc(t.outcome||t.kind)}</p><p>评价对象：${esc((t.evaluation_population||t.node_order||[]).join('、'))}</p><p>背景／时期：${esc(t.context||'以原始研究说明为准')}</p><details><summary>核对完整目标与权重</summary><pre>${esc(JSON.stringify(t,null,2))}</pre></details></div>`;}
 for(const [name,sheet] of Object.entries(r.review_sheets||{})){
  const record=records[name]||{};
  const title=labels[name]||(methodNames[name.split('.')[0]]||name.split('.')[0])+(name.endsWith('.science_review')?' · 科学条件':' · 目标和条件交接');
  html+=`<details class="review-sheet" open><summary>${esc(title)}</summary>`;
  if(sheet.correspondence)html+=`<pre>${esc(JSON.stringify(sheet.correspondence,null,2))}</pre>`;
  if(sheet.instruction)html+=`<p class="muted">${esc(sheet.instruction)}</p>`;
  for(const [path,d] of Object.entries(record.decisions||{})){
   const field=sheet.fields?.[path]||{},id='r'+rowBindings.length;rowBindings.push({id,name,path});
   const obj=typeof d==='object',catalog=sheet.source_catalog||{};
   const hints=(field.actual_citations||[]).map(c=>c.ref).concat(Object.values(field.citation_groups||{}).flat());
   const refs=[...new Set(hints)].filter(x=>x in catalog);
   html+=`<article class="review-row" id="${id}"><h4>${esc(rowTitle(path,field))}</h4>`;
   if(field.definition?.excludes)html+=`<div class="muted">${esc(field.definition.excludes)}</div>`;
   if(field.candidate!==undefined)html+=path===''?`<details><summary>完整候选（用于检查遗漏）</summary><pre>${esc(claim(field.candidate))}</pre></details>`:`<div class="candidate">${esc(claim(field.candidate))}</div>`;
   if(sheet.notes?.[path])html+=`<div class="candidate">${esc(claim(sheet.notes[path]))}</div>`;
   if(sheet.changes?.[path])html+=`<pre>${esc(JSON.stringify(sheet.changes[path],null,2))}</pre>`;
   if(field.explicit_definitions&&Object.keys(field.explicit_definitions).length)html+=`<details><summary>共同定义与依赖证据</summary><pre>${esc(JSON.stringify(field.explicit_definitions,null,2))}</pre></details>`;
   if(refs.length)html+=`<details><summary>模型实际引用的原文</summary><div class="sources">${refs.map(x=>`[${esc(x)}] ${esc(sourceText(catalog[x]))}`).join('\n\n')}</div></details>`;
   if(obj&&'field_role' in d){html+='<div class="axes">';for(const dim of ['field_role','value_state','source_coverage'])html+=`<label>${labels[dim]}${selects(['PENDING','ACCEPTED','REJECTED'],d[dim],`data-dimension="${dim}"`)}</label>`;html+='</div>';}
   else if(obj)html+=selects(sheet.changes?['PENDING','ACCEPTED','REJECTED']:['PENDING','MATERIAL_GAP','READING_ERROR','NONBLOCKING_COMMENT','DEFER_TO_MATHEMATICS'],d.disposition,'data-dimension="disposition"');
   else html+=selects(['PENDING','ACCEPTED','REJECTED'],d,'data-dimension="simple"');
   if(obj){html+=`<textarea class="reason" rows="2" placeholder="说明本条判断的原文依据，至少 12 个字符"></textarea><div class="row-tools"><button type="button" class="text-button reuse-reason">采用顶部的审核说明</button></div><details><summary>本条审核所依据的来源（勾选）</summary><div class="source-select">${Object.entries(catalog).map(([key,val])=>`<label title="${esc(sourceText(val))}"><input type="checkbox" data-ref="${esc(key)}" ${refs.includes(key)?'checked':''}>${esc(key)}</label>`).join('')}</div><div class="sources">${Object.entries(catalog).map(([key,val])=>`[${esc(key)}] ${esc(sourceText(val))}`).join('\n\n')}</div></details>`;}
   html+='</article>';
  }
  if('disposition' in record&&!record.decisions){html+=`<div data-information="${esc(name)}">${selects(['PENDING','ACCEPTED','REJECTED'],'PENDING','data-info-disposition')}<label>原始信息表来源编号（逗号分隔）<input data-table-refs placeholder="从下方来源目录选择"></label><label>仅支持定义解释的来源编号（逗号分隔）<input data-support-refs></label><pre>${esc(JSON.stringify(sheet.source_catalog,null,2))}</pre></div>`;}
  if(record.material_decisions)html+='<p class="muted">本记录含独立材料覆盖判断，请在下方“完整审核记录”中逐项填写 material_decisions。</p>';
  html+='</details>';
 }
 $('#review-fields').innerHTML=html;$('#review-json').value=JSON.stringify(records,null,2);
 $('#review-fields').onclick=e=>{if(e.target.classList.contains('reuse-reason'))e.target.closest('.review-row').querySelector('.reason').value=$('#review-evidence').value;};
}
// This button is a user review action, not an automatic semantic verifier.
// It produces the same bound records as the detailed form. Rejections never
// become approvals, and unknown scientific conditions still stop in the Core adapter.
$('#confirm-summary').onclick=async()=>{
 if(reviewSubmitting)return;
 if(current?.review_kind==='information'){
  try{if(current.busy)throw Error('正在处理，请稍候。');const answer=informationRecords(current,informationChoices);reviewSubmitting=true;$('#confirm-summary').disabled=true;await api('/api/action',{id:runId,action:'review',payload:{kind:'information',records:answer}});poll();}
  catch(e){$('#review-message').textContent=e.message;}finally{reviewSubmitting=false;}return;
 }
 try{
  if(!current||!reviewSummary(current).compact_confirmation_available||current.busy)throw Error('本阶段需要处理具体问题，不能集中确认。');
  if($('#use-review-json').checked)throw Error('你正在编辑独立审核记录，请用下方按钮提交该记录。');
  if(document.querySelector('#review-fields select option[value="REJECTED"]:checked'))throw Error('存在已拒绝项，集中确认不会覆盖它。请展开处理或提交拒绝。');
  const reviewer=$('#reviewer').value.trim()||'Local browser user';
  if(reviewer.length<3){$('#review-details').open=true;$('#reviewer').focus();throw Error('自填的记录标识至少需要 3 个字符，也可以留空。');}
  const purpose={query:'我已核对问题摘要及原材料，确认本次比较、评价对象和研究口径。',source:'我已核对事实摘要与原材料，确认字段解释和引用，未在此批准科学条件。',changes:'我已逐项查看本页展示的复核前后变化，确认与原材料一致；本操作不批准科学条件。',science:'我确认本研究采用摘要及展开记录中列出的科学条件，按当前材料进行识别。',data:'我已核对配套数据与目标的对应及估计适用条件，同意继续计算。'}[current.review_kind];
  const evidence=$('#review-evidence').value.trim()||purpose;
  const answer=structuredClone(records);
  for(const [name,record] of Object.entries(answer)){
   record.reviewer=reviewer;record.evidence=evidence;
   const sheet=current.review_sheets[name],catalog=sheet.source_catalog||{};
   for(const [path,decision] of Object.entries(record.decisions)){
    const binding=rowBindings.find(x=>x.name===name&&x.path===path),el=$('#'+binding.id);
    if(typeof decision==='object'){
     let refs=Array.from(el.querySelectorAll('[data-ref]:checked')).map(x=>x.dataset.ref);
     // For absence/coverage review, the user attests to the current materials.
     // These are reviewer sources only; model citations remain byte-for-byte unchanged.
     if(!refs.length)refs=Object.keys(catalog);
     if(!refs.length)throw Error('缺少可核对的原材料，请展开查看。');
     Object.assign(decision,sheet.changes?{disposition:'ACCEPTED',reason:el.querySelector('.reason').value.trim()||evidence,source_ids:refs}:
      {field_role:'ACCEPTED',value_state:'ACCEPTED',source_coverage:'ACCEPTED',reason:el.querySelector('.reason').value.trim()||evidence,source_ids:refs});
    }else record.decisions[path]='ACCEPTED';
   }
  }
  reviewSubmitting=true;$('#confirm-summary').disabled=true;$('#submit-review').disabled=true;
  await api('/api/action',{id:runId,action:'review',payload:{kind:current.review_kind,records:answer}});await poll();
 }catch(e){$('#review-message').textContent=e.message;}
 finally{reviewSubmitting=false;$('#confirm-summary').disabled=!current||current.busy||!reviewSummary(current).compact_confirmation_available;$('#submit-review').disabled=!!current?.busy;}
};
$('#request-recheck').onclick=async()=>{
 if(reviewSubmitting||current?.busy)return;
 try{
  if(!current?.recheck_preview?.available)throw Error('本轮尚不能一键复核，请查看上方具体说明。');
  reviewSubmitting=true;$('#request-recheck').disabled=true;
  await api('/api/action',{id:runId,action:'recheck',payload:{binding_sha256:current.recheck_preview.binding_sha256}});
  await poll();
 }catch(e){$('#review-message').textContent=e.message;}
 finally{reviewSubmitting=false;$('#request-recheck').disabled=!!current?.busy||!current?.recheck_preview?.available;}
};
$('#submit-review').onclick=async()=>{
 try{let answer;if($('#use-review-json').checked)answer=JSON.parse($('#review-json').value);else{
  answer=structuredClone(records);for(const record of Object.values(answer)){record.reviewer=$('#reviewer').value.trim();record.evidence=$('#review-evidence').value.trim();}
  for(const {id,name,path} of rowBindings){const el=$('#'+id),d=answer[name].decisions[path];for(const field of el.querySelectorAll('[data-dimension]')){if(field.dataset.dimension==='simple')answer[name].decisions[path]=field.value;else d[field.dataset.dimension]=field.value;}if(typeof d==='object'){d.reason=el.querySelector('.reason').value.trim();d.source_ids=Array.from(el.querySelectorAll('[data-ref]:checked')).map(x=>x.dataset.ref);}}
  for(const el of document.querySelectorAll('[data-information]')){const d=answer[el.dataset.information];d.disposition=el.querySelector('[data-info-disposition]').value;for(const [field,selector] of [['table_source_ids','[data-table-refs]'],['supporting_source_ids','[data-support-refs]']])d[field]=el.querySelector(selector).value.split(/[,，\s]+/).filter(Boolean);}
 }
 $('#submit-review').disabled=true;await api('/api/action',{id:runId,action:'review',payload:{kind:current.review_kind,records:answer}});poll();
 }catch(e){$('#run-error').hidden=false;$('#run-error').textContent=e.message;}finally{$('#submit-review').disabled=false;}
};
function mathText(x){return `<mtext>${esc(x)}</mtext>`;}
function policyText(policy){const pairs=Object.entries(policy||{});return [1,0].map(level=>{const nodes=pairs.filter(([,v])=>v===level).map(([n])=>n);return nodes.length?(pairs.length<=6?nodes.join('、'):nodes.length+' 个对象')+(level?'接受处理':'不接受处理'):null;}).filter(Boolean).join('；');}
function peerText(kind,state){
 if(kind==='THREE_LEVEL_TREATED_NEIGHBOR_FRACTION')return {0:'启用的邻居不足三分之一',1:'启用的邻居至少三分之一且不足三分之二',2:'启用的邻居至少三分之二'}[state]||'同伴状态待明确';
 if(kind==='PRETREATMENT_CORE_COLLABORATOR_MAJORITY')return {0:'预先指定的核心伙伴中至多一半启用',1:'预先指定的核心伙伴中超过一半启用'}[state]||'同伴状态待明确';
 if(kind==='STRICT_MAJORITY_TIES_LOW')return {0:'相邻对象中至多一半接受处理',1:'相邻对象中超过一半接受处理'}[state]||'同伴状态待明确';
 if(kind==='ANY_TREATED_NEIGHBOR')return {0:'没有相邻对象接受处理',1:'至少一名相邻对象接受处理'}[state]||'同伴状态待明确';
 if(kind==='EXACT_TREATED_NEIGHBOR_COUNT')return `恰好 ${state} 名相邻对象接受处理`;
 return '同伴状态 '+state;
}
function expectation(own,peer,policy){const condition=policy!==undefined?`T = (${policy.join(', ')})`:`Tᵢ = ${own}, Sᵢ = ${peer}`;return `<mi mathvariant="double-struck">E</mi><mo>[</mo><msubsup><mi>Y</mi><mi>i</mi><mtext>obs</mtext></msubsup><mo>∣</mo>${mathText(condition+', W')}<mo>]</mo>`;}
function numberMath(x){const s=String(x);return /^-?\d+\/\d+$/.test(s)?'<mfrac>'+s.split('/').map(v=>'<mn>'+esc(v)+'</mn>').join('')+'</mfrac>':mathText(s);}
function dagSymbols(f){
 if(f.operation==='CLASSICAL_FRONTDOOR')return [
  {variable:f.free_values.intervention_value.variable,symbol:'X',value:'x',role:'处理'},
  {variable:f.free_values.outcome_value.variable,symbol:'Y',value:'y',role:'结果'},
  {variable:f.expression.bind.variable,symbol:'M',value:'m',role:'中介'}];
 if(['BACKDOOR_ADJUSTMENT','COVARIATE_ADJUSTMENT'].includes(f.operation))return [
  {variable:f.treatment,symbol:'X',value:'x',role:'处理'},
  {variable:f.outcome,symbol:'Y',value:'y',role:'结果'},
  ...f.sum_over.map((variable,i)=>({variable,symbol:f.sum_over.length===1?'Z':'Z'+(i+1),value:f.sum_over.length===1?'z':'z'+(i+1),role:'调整变量'}))];
 return [];
}
function symbolLegend(f){
 const rows=dagSymbols(f);
 return rows.length?'<dl class="formula-symbols">'+rows.map(x=>`<div><dt>${esc(x.symbol)}</dt><dd>${esc(x.variable)} <small>${esc(x.role)}</small></dd></div>`).join('')+'</dl><p class="muted">小写字母表示对应变量的取值'+(f.operation==='CLASSICAL_FRONTDOOR'?'；x′ 是内层求和的处理取值，与干预值 x 区分':'')+'。</p>':'';
}
function dagFormula(f){
 const symbols=dagSymbols(f),alias=new Map(symbols.map(s=>[s.variable,s.value]));
 const variable=x=>{if(!alias.has(x))throw Error('Unbound certified variable');return alias.get(x);};
 const P=(out,given=[])=>'<mrow><mi>P</mi><mo stretchy="false">(</mo>'+mathText(out.join(', '))+(given.length?'<mo stretchy="false">∣</mo>'+mathText(given.join(', ')):'')+'<mo stretchy="false">)</mo></mrow>';
 const sum=(v,body)=>'<munder><mo>∑</mo>'+mathText(v)+'</munder>'+body;
 if(['BACKDOOR_ADJUSTMENT','COVARIATE_ADJUSTMENT'].includes(f.operation)){
  const body=P(f.conditional.outcomes.map(variable),f.conditional.given.map(variable))+(f.sum_over.length?P(f.marginal.variables.map(variable)):'');
  return P([variable(f.outcome)],['do('+variable(f.treatment)+')'])+'<mo>=</mo>'+(f.sum_over.length?sum(f.sum_over.map(variable).join(', '),body):body);
 }
 if(f.operation==='CLASSICAL_FRONTDOOR'){
  const roles={intervention_value:'x',outcome_value:'y',mediator_value:'m',treatment_marginal_value:'x′'};
  const val=x=>{variable(x.variable);if(!roles[x.value_role])throw Error('Unbound certified value role');return roles[x.value_role];};
  function expr(e){
   if(e.operation==='SUM'){variable(e.bind.variable);return sum(roles[e.bind.role],'<mo>[</mo>'+expr(e.summand)+'<mo>]</mo>');}
   if(e.operation==='PRODUCT')return e.factors.map(expr).join('<mo>·</mo>');
   if(['CONDITIONAL_PROBABILITY','PROBABILITY'].includes(e.operation))return P(e.outcomes.map(val),(e.given||[]).map(val));
   throw Error('Unsupported certified expression');
  }
  return P([variable(f.free_values.outcome_value.variable)],['do('+variable(f.free_values.intervention_value.variable)+')'])+'<mo>=</mo>'+expr(f.expression);
 }
 return '';
}
function formulaHTML(result){const c=result.mathematical_claim||{},t=c.target||{};let content='';
 const cert=result.certificate||{},sum='<munder><mo>∑</mo><mrow><mi>i</mi><mo>∈</mo><mi>V</mi></mrow></munder><msub><mi>w</mi><mi>i</mi></msub>';
 if(c.functional)content=dagFormula(c.functional);
 if(c.representation==='EXACT_IDENTIFIED_INTERVAL'&&Array.isArray(c.interval)&&c.interval.length===2)content='<mi>'+ (t.kind?.includes('CONTRAST')?'Δ':'θ') +'</mi><mo>∈</mo><mo>[</mo>'+numberMath(c.interval[0])+'<mo>,</mo>'+numberMath(c.interval[1])+'<mo>]</mo>';
 else if(c.kind==='POINT'&&['R2','R3_MEAN_SIGNATURE'].includes(cert.route)&&t.assignment)content='<mi>θ</mi><mo>=</mo>'+sum+expectation('aᵢ','gᵢ(a)');
 else if(c.kind==='POINT'&&cert.route==='R3_FULL_ASSIGNMENT'&&t.assignment)content='<mi>θ</mi><mo>=</mo>'+sum+expectation(null,null,t.assignment);
 else if(c.kind==='POINT'&&t.kind==='FIXED_FULL_ASSIGNMENT_POLICY_MEAN'&&result.certificate?.route?.startsWith('R1B_'))content='<mi>θ</mi><mo>=</mo><munder><mo>∑</mo><mrow><mi>i</mi><mo>∈</mo><mi>V</mi></mrow></munder><msub><mi>w</mi><mi>i</mi></msub>'+expectation(null,null,t.assignment);
 else if(c.kind==='POINT'&&t.kind==='FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST'&&cert.terms?.length)content='<mi>Δ</mi><mo>=</mo>'+cert.terms.map(x=>'<mo>(</mo>'+numberMath(x.coefficient)+'<mo>)</mo>'+mathText(x.observable)).join('<mo>+</mo>');
 else if(c.kind==='POINT'&&['R3_EXPOSURE_ADJUSTED_EFFECTS','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'].includes(cert.route)){
  const variable=cert.route==='R3_EXPOSURE_ADJUSTED_EFFECTS'?'B':'Cᵢ';
  const mean=a=>'<mi mathvariant="double-struck">E</mi><mo>[</mo>'+mathText('Yᵢ obs')+'<mo>∣</mo>'+mathText(`Tᵢ=${a[0]}, Sᵢ=${a[1]}, ${variable}=c, W`)+'<mo>]</mo>';
  content='<mi>τ</mi><mo>=</mo>'+sum+'<munder><mo>∑</mo><mi>c</mi></munder>'+mathText(`P(${variable}=c ∣ W)`)+'<mo>[</mo>'+mean(t.first)+'<mo>−</mo>'+mean(t.second)+'<mo>]</mo>';
 }
 else if(c.kind==='POINT'&&t.kind==='SINGLE_ARM_MEAN')content='<mi>θ</mi><mo>=</mo>'+expectation(t.first[0],t.first[1]);
 else if(c.kind==='POINT'&&t.kind==='FINITE_POLICY_MEAN')content='<mi>θ</mi><mo>=</mo>'+t.policies.map(p=>numberMath(p.weight)+'<mo>·</mo><mo>(</mo>'+sum+expectation(null,null,p.assignment)+'<mo>)</mo>').join('<mo>+</mo>');
 else if(c.kind==='POINT'&&['DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT'].includes(t.kind)&&t.first&&t.second)content='<mi>τ</mi><mo>=</mo><munder><mo>∑</mo><mrow><mi>i</mi><mo>∈</mo><mi>V</mi></mrow></munder><msub><mi>w</mi><mi>i</mi></msub><mo>(</mo>'+expectation(t.first[0],t.first[1])+ '<mo>−</mo>'+expectation(t.second[0],t.second[1])+'<mo>)</mo>';
 else if(!content&&typeof c.expression==='string')content=mathText(c.expression);
 const f=c.functional,legend=f?symbolLegend(f):'';
 return content?`<div class="formula"><math display="block"><mrow>${content}</mrow></math></div>${legend}<details class="formula-origin muted"><summary>公式来源</summary><p>按本次识别库返回的目标、公式和证书展示。</p></details>`:'';
}
function populationHTML(t){const nodes=t.evaluation_population||t.population||(t.unit_weights?(t.node_order||[]).filter((n,i)=>!['0','0/1'].includes(String(t.unit_weights[i]))):t.node_order)||[];const names=esc(nodes.join('、'));return nodes.length>8?`<details><summary>${nodes.length} 个评价对象（展开名单）</summary><p>${names}</p></details>`:`<p>${names}</p>`;}
function comparisonText(t){
 if(t.kind==='SINGLE_ARM_MEAN')return `本人${t.first[0]?'接受':'不接受'}处理，${peerText(t.exposure,t.first[1])}时的平均结果。其余安排按原设计条件概率平均。`;
 if(t.kind==='FINITE_POLICY_MEAN')return t.policies.map(p=>'以概率 '+p.weight+' 采用 '+policyText(Object.fromEntries(t.node_order.map((n,i)=>[n,p.assignment[i]])))).join('；');
 if(t.kind==='INTERVENTIONAL_DISTRIBUTION')return '设定“'+t.treatment+'”，其余机制保持不变，求“'+t.outcome+'”的干预分布。';
 if(['DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT'].includes(t.kind)&&t.first&&t.second){
  const arm=a=>({0:'本人不接受处理',1:'本人接受处理'}[a[0]]||'本人状态 '+a[0])+'，'+peerText(t.exposure,a[1]);
  return arm(t.first)+'；减去：'+arm(t.second)+'。';
 }
 const policy=a=>policyText(Object.fromEntries((t.node_order||[]).map((n,i)=>[n,a[i]])));
 if(t.first&&t.second)return '第一方案：'+policy(t.first)+'；减去第二方案：'+policy(t.second)+'。';
 return t.assignment?'评价以下安排下的平均结果：'+policy(t.assignment)+'。':'以本次目标定义为准。';
}
function formulaGuide(t,c={}){
 if(c.representation==='EXACT_IDENTIFIED_INTERVAL')return '<p class="muted">'+(t.kind?.includes('CONTRAST')?'Δ 表示第一方案减去第二方案的平均结果差。':'θ 表示所指定政策下的平均结果。')+'</p>';
 if(t.kind==='SINGLE_ARM_MEAN')return '<p class="muted">i 是选定对象，Sᵢ 是所述同伴状态。此均值按原设计在该状态下的条件分配律平均其余安排，不把其余人逐一固定。</p>';
 if(t.kind==='FINITE_POLICY_MEAN')return '<p class="muted">外层权重是未来选择完整方案的概率，内层 wᵢ 是评价对象权重；两者均不同于历史试点的分配概率。</p>';
 if(t.averaging==='SHARED_PRETREATMENT_STRATUM'||t.averaging==='OWN_AND_NEIGHBOR_BINARY_FEATURE')return '<p class="muted">wᵢ 是评价对象权重；B 是共同处理前分层，Cᵢ 是本人二元特征与全部邻居中特征为1的人数。按各自总体分布求和；分层权重不是历史处理概率。</p>';
 if(!['DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT','FIXED_FULL_ASSIGNMENT_POLICY_MEAN','FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST'].includes(t.kind))return '';
 const local=['DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT'].includes(t.kind);
 const weights=t.unit_weights||[];
 return '<p class="muted">'+esc('V 是评价名单，wᵢ 是本次采用的对象权重'+(weights.length&&new Set(weights).size===1?'（本次每个对象为 '+weights[0]+'）':'')+'；Yᵢ 是该对象的结果，T 是处理安排，W 是本次固定背景。'+(local?'Tᵢ 是本人状态，Sᵢ 是同伴状态。':'')+(t.exposure==='STRICT_MAJORITY_TIES_LOW'?'同伴状态 1 表示相邻对象中超过一半接受处理，0 表示至多一半。':t.exposure==='ANY_TREATED_NEIGHBOR'?'同伴状态 1 表示至少一名邻居接受处理，0 表示无人接受处理。':t.exposure==='EXACT_TREATED_NEIGHBOR_COUNT'?'同伴状态就是接受处理的邻居人数。':''))+'</p>'+(t.remaining_assignment==='ORIGINAL_DESIGN_CONDITIONAL'?'<p class="muted">未指定的其余安排按原随机设计在对应条件下平均；这不是把每位同伴的安排逐一固定。</p>':'');
}
function certifiedAssumptions(result){
 const used=new Set();
 function visit(c){
  if(!c||typeof c!=='object')return;
  for(const x of c.assumptions_used||[])if(typeof x==='string')used.add(x);
  for(const child of c.results||[])visit(child);
  if(c.certificate)visit(c.certificate);
 }
 visit(result.certificate);
 const record=result.condition_record;
 if(result.independent_replay===true&&record?.origin==='EXECUTED_CERTIFICATES'&&record.source_batch_sha256&&record.source_batch_sha256===result.certificate?.source_batch_sha256)
  for(const key of record.keys||[])if(typeof key==='string')used.add(key);
 for(const answer of result.answers||[]){
  visit(answer.certificate);
  // Composition summaries list common assumptions. The replayed native
  // anchor also owns design-specific conditions, e.g. the first-stage exclusion.
  if(result.independent_replay===true&&answer.independent_replay===true)
   visit(answer.native_evidence?.result?.source_batch?.anchor?.result);
 }
 return [...used];
}
function resultConditions(result){
 const summary=result.independent_replay===true?result.web_review_summary:null;
 const lines=summary?.contract==='registered-web-review-1'?summary.cards?.[1]?.lines:[];
 if(lines?.length)return lines.map((text,i)=>{
  const item=summary.condition_items?.[i];
  return item?.text===text?item:conditionEntry(text);
 });
 // Older results use only the requirements actually recorded by their certificates.
 // An example author's prose is never a substitute for executed evidence.
 return certifiedAssumptions(result).map(key=>conditionTerms[key]||{key,label:labels[key]||key,text:labels[key]||key,category:'science'});
}
function resultConditionsHTML(result){
 const items=resultConditions(result);if(!items.length)return '';
 const groups=[['science','采用的研究假设'],['information','本次使用的信息与范围'],['other','其他已记录条件']];
 const t=result.mathematical_claim?.target||{};
 const context=[t.treatment?'本题的处理：'+t.treatment:'',t.outcome?'关注的结果：'+t.outcome:''].filter(Boolean);
 return '<section class="adopted-conditions"><h4>本次结论依赖的条件</h4><div class="condition-groups">'+groups.map(([kind,title])=>{
  const rows=items.filter(x=>(x.category||'information')===kind);
  return rows.length?`<div><h5>${title}</h5><ul>${rows.map(x=>`<li>${conditionHeading(x)}</li>`).join('')}</ul></div>`:'';
 }).join('')+'</div><details class="condition-definitions"><summary>这些假设在本题中是什么意思？</summary>'+
 (context.length?'<p class="condition-context">'+context.map(esc).join('<br>')+'</p>':'')+
 '<ul>'+items.map(x=>`<li class="condition-explanation">${conditionDetailHTML(x)}</li>`).join('')+'</ul></details><p class="muted">结论以这些条件成立为前提。证书验证不证明现实中的假设一定成立。</p></section>';
}
function resultHTML(result,estimate){
 const state=result.state||result.kind,good=['POINT','PARTIAL'].includes(state),claimData=result.mathematical_claim;
 const reason=result.reason_code||'',readingReasons={
  TARGET_FIRST_CONTRACT_REJECTED:['模型回复格式有误','模型漏填或错填了必要内容，识别尚未开始。具体字段见详细记录。'],
  COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS:['研究结构需要复核','模型混用了对象关系和变量因果关系，需要重新核对两类图的含义。'],
  TARGET_AVERAGING_AND_POPULATION_OPERATOR_MISMATCH:['目标与信息范围需要复核','模型读到的平均方式与可用信息不一致，需要核对原文。']};
 const title=readingReasons[reason]?.[0]||(reason.startsWith('DECLARED_MODEL_EXCLUDES:')||reason.startsWith('REQUIRED_ASSUMPTION_NOT_ADOPTED:')?'当前方法所需条件未采用':reason.startsWith('ADDITIONAL_')?'附加声明尚未处理':names[state]||state);
 let html=`<article class="result-card ${good?'':'blocked'}"><div class="result-header"><h3>${esc(title)}</h3><span class="tag">${esc(result.independent_replay?'证书独立重放通过':good?'请核对验证记录':'未生成认证结论')}</span></div>`;
 if(result.independent_replay===true&&state==='POINT')html+='<p class="identification-conclusion">在下列假设下，本题目标可以由可用的总体信息唯一确定。下面的公式供后续估计使用。</p>';
 if(claimData){const t=claimData.target||{};html+=`<div class="result-facts"><div><b>关注的结果与背景</b><p>${esc(t.outcome||t.kind||'见数学目标')}</p><p class="muted">${esc(t.context||'')}</p>${t.treatment?`<p class="muted">处理含义：${esc(t.treatment)}</p>`:''}</div><div><b>评价对象与比较</b>${populationHTML(t)}<p>${esc(comparisonText(t))}</p></div></div><h4>识别公式</h4>${formulaHTML(result)}${formulaGuide(t,claimData)}`;if(state==='POINT')html+='<p class="muted">这是识别公式，效应数值需在估计阶段计算。</p>';}
 if(claimData?.representation==='EXACT_IDENTIFIED_INTERVAL')html+=`<p>${claimData.sharp===true?'在所列假设下，这是最紧的上下界（sharp bounds）。':'是否为最紧的上下界，请查看验证记录。'}${claimData.informative===false?'现有信息没有进一步缩小预先给定的范围。':''}</p>`;
 if(result.reason_code)html+=`<p><b>当前情况：</b>${esc({NEEDS_INPUT:'缺少必要信息，请回答页面列出的具体问题。',READING_RECHECK_REQUIRED:'模型的读取结果需要重新核对，识别尚未完成。',CHECK_BLOCKED:'读取或条件检查未通过，暂不能给出识别结果。',UNSUPPORTED:'当前识别方法还不能处理这类问题。',ADAPTER_NOT_CONNECTED:'已有处理流程尚未接通这类目标或条件。',REVIEW_REQUIRED:'有一项研究条件仍需明确。'}[state]||'本次分析未完成，具体原因见详细记录。')}</p>`;
 if(readingReasons[reason])html+=`<p>${esc(readingReasons[reason][1])}</p>`;
 if(result.processing_explanation)html+=`<p>${esc(result.processing_explanation)}</p>`;
 const choices=(result.assumption_choices_review?.retained||[]).filter(c=>c.required===false);
 const choiceLabels={MEAN_EXPOSURE_SUFFICIENCY:'同伴分组的均值充分性',OUTCOME_EXPOSURE_SUFFICIENCY:'同伴分组确定每个潜在结果的假设'};
 if(choices.length)html+='<p class="muted">'+choices.map(c=>esc(choiceLabels[c.condition]?('本次'+(c.status==='NOT_ADOPTED'?'不采用':'尚未决定是否采用')+choiceLabels[c.condition]+'；所用方法不需要这项假设。'):c.condition)).join('；')+'</p>';
 const questions=result.clarification_questions||[];if(questions.length)html+='<ul>'+questions.map(q=>`<li>${esc(clarificationText(q,result))}</li>`).join('')+'</ul>';
 html+=resultConditionsHTML(result);
 if(!good)html+='<p class="muted">'+(state==='NEEDS_INPUT'?'不清楚或尚未决定的内容，请注明。':'本次停止不代表已证明不可识别。')+'</p>';
 html+=`<details><summary>查看公式与验证记录</summary><pre>${esc(JSON.stringify(result,null,2))}</pre></details></article>`;
 return html;
}
async function init(){try{await health();examples=await api('/api/examples');renderExamples();const match=location.hash.match(/^#run=([a-f0-9]{32})$/);if(match){runId=match[1];$('#workspace').hidden=false;poll();}}catch(e){$('#connection').textContent='本地服务未连接';message('请在仓库根目录运行 python demo/serve.py。'+e.message,true);}}
init();
