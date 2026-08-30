(async()=>{
const $=id=>document.getElementById(id);
let data,state,nodeStarted;
const ordered=['recognition','cultures','antibiotics','fluids','reassessment','vasopressor','source_control'];
try{
  data=await (await fetch('/api/scenario/septic-shock')).json();
  const p=data.patient;
  $('patient-grid').innerHTML=[['Edad',p.edad+' años'],['Peso',p.peso+' kg'],['PA',p.pa+' mmHg'],['PAM',p.pam+' mmHg'],['FC',p.fc+' lpm'],['FR',p.fr+' rpm'],['SpO₂',p.spo2+' %'],['T°',p.temp+' °C'],['Lactato',p.lactato+' mmol/L'],['Creatinina',p.creatinina+' mg/dL'],['Plaquetas',p.plaquetas+' x10³/µL'],['PaFi',p.pafi]].map(([a,b])=>`<div><strong>${a}</strong><span>${b}</span></div>`).join('');
  $('phase').textContent=data.phase;
  await start();
}catch(e){ $('question').textContent='No fue posible iniciar la simulación. Ejecuta primero: python app.py'; console.error(e);}

async function start(){
 const r=await fetch('/api/session/start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
 const j=await r.json(); state=j.state; $('session-status').textContent='Sesión activa'; renderNode(state.node);
}
function renderNode(id){
 if(!id){finish();return;}
 const n=data.nodes[id]; nodeStarted=performance.now(); $('node-title').textContent=n.title; $('question').textContent=n.prompt;
 const idx=ordered.indexOf(id); $('progress').textContent=`Nodo ${idx+1} de ${ordered.length}`;
 $('choices').innerHTML=n.options.map(o=>`<button class="choice" data-choice="${escapeHtml(o)}">${escapeHtml(o)}</button>`).join('');
 document.querySelectorAll('.choice').forEach(b=>b.onclick=()=>choose(b.dataset.choice,b));
}
async function choose(choice,button){
 document.querySelectorAll('.choice').forEach(b=>b.disabled=true);
 const elapsed=Math.floor((performance.now()-nodeStarted)/1000); $('timer').textContent=fmt(elapsed);
 const r=await fetch('/api/session/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:state.id,node_id:state.node,choice,elapsed_seconds:elapsed})});
 const j=await r.json(); const result=j.result; state=j.state;
 document.querySelectorAll('.choice').forEach(b=>{if(b.textContent===data.nodes[state.decisions[state.decisions.length-1].node].expected)b.classList.add('correct')});
 button.classList.add(result.correct?'correct':'incorrect');
 $('feedback-content').innerHTML=`<div class="${result.correct?'good':'bad'}"><strong>${result.correct?'✓ Decisión adecuada para este nodo':'✕ Desviación educativa'}</strong><p>${data.nodes[state.decisions[state.decisions.length-1].node].feedback}</p><p>${result.consequence}</p><p><b>Esperada:</b> ${escapeHtml(data.nodes[state.decisions[state.decisions.length-1].node].expected)}</p><p><b>Tiempo:</b> ${fmt(elapsed)}</p></div>`;
 $('pam').textContent=result.physiology.pam; $('lactato').textContent=result.physiology.lactato; $('score').textContent=state.score; $('delay').textContent=state.delay_minutes;
 renderTrace();
 setTimeout(()=>{ if(result.next_node===state.decisions[state.decisions.length-1].node && !result.correct){renderNode(result.next_node)} else {renderNode(result.next_node);} }, result.correct?700:1000);
}
function renderTrace(){$('trace-list').innerHTML=state.decisions.map((d,i)=>`<div class="trace-item"><b>${i+1}. ${escapeHtml(data.nodes[d.node].title)}</b><span>${escapeHtml(d.choice)}</span><span>${d.correct?'✓ Alineada':'✕ Desviación'} · ${fmt(d.elapsed_seconds)}</span></div>`).join('');}
function finish(){
 $('completion').classList.remove('hidden'); $('completion-content').innerHTML=`<div class="final-score">${state.score}</div><p>La sesión terminó con <b>${state.decisions.filter(d=>d.correct).length}</b> decisiones alineadas y <b>${state.decisions.filter(d=>!d.correct).length}</b> desviaciones educativas.</p><p>Tiempo acumulado: <b>${fmt(state.elapsed_seconds)}</b>. Retraso simulado: <b>${state.delay_minutes} min</b>.</p><p><b>Debriefing:</b> revisa cada nodo, la secuencia de acciones y cómo una decisión cambió el estado fisiológico del escenario.</p>`; $('session-status').textContent='Sesión completada'; $('choices').innerHTML=''; $('question').textContent='Simulación finalizada.';
}
$('restart').onclick=()=>location.reload();
function fmt(s){s=Math.max(0,Math.round(s));return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
})();
