let scenario=null,sid=null,category='observe',soundOn=false,paused=false;
let simStart=Date.now(),pauseStarted=null,simPausedAccum=0,lastAction=Date.now(),score=0,history=[],eventSeen=new Set();
let audioCtx=null,masterGain=null,ambientNode=null,ambientGain=null,heartTimer=null,alarmTimer=null,voiceEnabled=false;
const categoryNames={observe:'Observación',investigate:'Información',intervene:'Intervención',reassess:'Reevaluación'};
const eventKind={nursing:'warn',labs:'info',clinical:'warn',deterioration:'danger',closure:'ok',monitor:'warn'};
const caseStatusMeta={en_curso:['Caso en curso',''],listo_para_cierre:['Listo para cierre','ready'],escalamiento_requerido:['Requiere escalamiento','critical']};
const alertKind={encouragement:'ok',consciousness:'warn',deterioration:'danger',closure:'ok'};
const voiceProfiles={
  'Enfermería':{rate:.97,pitch:1.18},
  'Laboratorio':{rate:.9,pitch:.88},
  'Equipo':{rate:1,pitch:1},
  'Monitor':{rate:1.08,pitch:.7},
  'Paciente':{rate:.82,pitch:1.32},
};
let lastAlarmSpoken=0;
let voiceQueue=[],speaking=false;
const vital={fc:125,bpSys:78,bpDia:45,spo2:88,rr:28,temp:39.2,map:56,lactate:4.8};
const historyVitals=[];
const $=id=>document.getElementById(id);
const app=async(url,opts={})=>{const r=await fetch(url,{...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});if(!r.ok)throw new Error(await r.text());return r.json()};

function ensureAudio(){
  if(audioCtx){ if(audioCtx.state==='suspended') audioCtx.resume(); return; }
  try{
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    masterGain=audioCtx.createGain(); masterGain.gain.value=.4; masterGain.connect(audioCtx.destination);
    if(audioCtx.state==='suspended') audioCtx.resume();
  }catch(e){audioCtx=null}
}
function setMasterGain(){if(masterGain) masterGain.gain.value=(+$('volumeRange').value/100)*.55}
function tone(freq=520,dur=.08,type='sine',gain=.08,when=0){
  if(!audioCtx||!soundOn)return;
  const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type=type;o.frequency.value=freq;o.connect(g);g.connect(masterGain);
  const t=audioCtx.currentTime+when;g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(Math.max(.001,gain),t+.01);g.gain.exponentialRampToValueAtTime(.0001,t+dur);o.start(t);o.stop(t+dur+.03);
}
function monitorBeep(){
  if(!$('monitorSound').checked||!soundOn)return;
  tone(vital.spo2<90?760:620,.055,'sine',.075);
}
function alarmPulse(){
  if(!$('alarmSound').checked||!soundOn)return;
  tone(780,.11,'square',.085);tone(590,.11,'square',.07,.14);
}
function startHeartLoop(){
  clearTimeout(heartTimer);
  const bpm=Math.max(45,Math.min(180,vital.fc));
  const interval=60000/bpm;
  heartTimer=setTimeout(()=>{monitorBeep();flashMonitor();startHeartLoop()},interval);
}
function flashMonitor(){const m=document.querySelector('.monitor-screen');if(!m)return;m.classList.remove('flash');void m.offsetWidth;m.classList.add('flash')}
function updateAlarm(){
  const bad=vital.map<65||vital.spo2<90;
  $('alarmLight').classList.toggle('hidden',!bad);
  $('alarmLabel').textContent=vital.map<65?'PAM baja':vital.spo2<90?'SpO₂ baja':'Alerta';
  if(bad&&soundOn){if(!alarmTimer) alarmTimer=setInterval(alarmPulse,4200)} else {clearInterval(alarmTimer);alarmTimer=null}
  if(bad&&voiceEnabled&&Date.now()-lastAlarmSpoken>20000){
    lastAlarmSpoken=Date.now();
    say(vital.map<65?'Alerta: presión arterial media baja.':'Alerta: saturación de oxígeno baja.','Monitor');
  }
}
function startAmbient(){
  if(!audioCtx||!$('ambientSound').checked||!soundOn||ambientNode)return;
  const buffer=audioCtx.createBuffer(1,audioCtx.sampleRate*2,audioCtx.sampleRate),data=buffer.getChannelData(0);
  for(let i=0;i<data.length;i++){data[i]=(Math.random()*2-1)*0.18}
  ambientNode=audioCtx.createBufferSource();ambientNode.buffer=buffer;ambientNode.loop=true;
  const filter=audioCtx.createBiquadFilter();filter.type='lowpass';filter.frequency.value=320;
  ambientGain=audioCtx.createGain();ambientGain.gain.value=.035;
  ambientNode.connect(filter);filter.connect(ambientGain);ambientGain.connect(masterGain);ambientNode.start();
}
function stopAmbient(){try{ambientNode?.stop()}catch(e){}ambientNode=null;ambientGain=null}
function say(text,source='Equipo'){
  voiceQueue.push({text,source});
  processVoiceQueue();
}
function processVoiceQueue(){
  if(speaking||!voiceQueue.length)return;
  const {text,source}=voiceQueue.shift();
  speaking=true;
  $('voiceBubble').classList.remove('hidden');$('voiceBubble').dataset.source=source;$('voiceBubble').classList.remove('pulse');void $('voiceBubble').offsetWidth;$('voiceBubble').classList.add('pulse');
  $('voiceSource').textContent=source;$('voiceText').textContent=text;
  logVoice(source,text);
  const endTurn=()=>{speaking=false;$('voiceBubble').classList.add('hidden');processVoiceQueue()};
  if(voiceEnabled&&'speechSynthesis' in window){
    const profile=voiceProfiles[source]||{rate:.95,pitch:1};
    const u=new SpeechSynthesisUtterance(text);
    u.lang='es-CO';u.rate=profile.rate;u.pitch=profile.pitch;u.volume=(+$('volumeRange').value/100);
    u.onend=endTurn;u.onerror=endTurn;
    window.speechSynthesis.speak(u);
  }else{
    setTimeout(endTurn,Math.min(5200,1400+text.length*38));
  }
}
function logVoice(source,text){
  const el=$('voiceLog');if(!el)return;
  const row=document.createElement('div');row.className='voice-log-item';
  row.innerHTML=`<div class="meta">${fmt(simSeconds())} · ${source}</div><span>${text}</span>`;
  el.prepend(row);
  while(el.children.length>40) el.removeChild(el.lastChild);
}
function simSeconds(){if(paused)return Math.max(0,Math.floor((pauseStarted-simStart-simPausedAccum)/1000));return Math.max(0,Math.floor((Date.now()-simStart-simPausedAccum)/1000))}
function fmt(s){return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}

async function start(){
  scenario=await app('/api/scenario/septic-shock');
  const s=await app('/api/session/start',{method:'POST',body:'{}'});sid=s.session_id;
  lastAction=Date.now();renderInfo();renderScenario();renderActions();renderVitals();renderTimeline();
  logEvent('Inicio','La paciente ingresa a la sala y se inicia la simulación.','ok');
  historyVitals.push({map:vital.map,lactate:vital.lactate});
  setInterval(tick,500);setupHotspots();
  updateAlarm();startHeartLoop();updateRoomClock();
}
function renderScenario(){$('nodeLabel').textContent='Inicio · evaluación inicial'}
function renderInfo(){const p=scenario.patient;$('infoList').innerHTML='';[['Alergia',p.alergias],['Leucocitos',p.leucocitos+' /µL'],['Creatinina',p.creatinina+' mg/dL'],['Plaquetas',p.plaquetas+' ×10³/µL'],['PaFi',p.pafi],['Foco',p.foco]].forEach(([k,v])=>{const d=document.createElement('div');d.className='info-row';d.innerHTML=`<span>${k}</span><strong>${v}</strong>`;$('infoList').appendChild(d)})}
function renderActions(){const list=scenario.actions[category]||[];$('actions').innerHTML='';list.forEach(item=>{const [id,label,desc]=item;const b=document.createElement('button');b.className='action';b.innerHTML=`<strong>${label}</strong><small>${desc}</small>`;b.addEventListener('click',()=>take(id,label));$('actions').appendChild(b)})}
function renderVitals(){
  $('fc').textContent=Math.round(vital.fc);$('bp').textContent=`${Math.round(vital.bpSys)}/${Math.round(vital.bpDia)}`;
  $('spo2').textContent=Math.round(vital.spo2);$('rr').textContent=Math.round(vital.rr);$('map').textContent=Math.round(vital.map);$('lactate').textContent=vital.lactate.toFixed(1);
  $('sceneFc').textContent=Math.round(vital.fc);$('ventRate').textContent=Math.round(Math.max(12,vital.rr-10));
  const unstable=vital.map<65||vital.spo2<90;const partial=!unstable&&vital.lactate>2;
  $('severityTag').textContent=unstable?'CRÍTICO':partial?'RESPUESTA PARCIAL':'ESTABILIZACIÓN';
  $('severityTag').className=unstable?'critical':'partial';
  $('hemoTag').textContent=vital.map<65?'Hipotensión':'PAM en mejoría';
  $('perfTag').textContent=vital.lactate>4?'Hipoperfusión':'Perfusión en recuperación';
  $('patientState').textContent=vital.map<55?'Somnolienta · respuesta disminuida':vital.map<65?'Somnolienta · responde a la voz':'Más alerta · responde mejor';
  $('respState').textContent=vital.spo2<90?'Respiración comprometida · hipoxemia':vital.rr>22?'Respiración rápida':'Respiración más regular';
  $('stateDot').classList.toggle('improving',!unstable);
  $('patientBody').classList.toggle('deteriorating',unstable);$('patientBody').classList.toggle('improving',!unstable);
  updateAlarm();
  historyVitals.push({map:vital.map,lactate:vital.lactate});drawTrends();
}
function drawTrends(){
  const pts=historyVitals.slice(-9);if(!pts.length)return;
  const mapMin=Math.min(...pts.map(x=>x.map)),mapMax=Math.max(...pts.map(x=>x.map));const lacMin=Math.min(...pts.map(x=>x.lactate)),lacMax=Math.max(...pts.map(x=>x.lactate));
  const scale=(v,min,max)=>58-((v-min)/(max-min||1))*42;
  const make=fn=>pts.map((x,i)=>`${(i/(Math.max(1,pts.length-1)))*300},${fn(x)}`).join(' ');
  $('trendPathMap').setAttribute('points',make(x=>scale(x.map,mapMin,mapMax)));
  $('trendPathLactate').setAttribute('points',make(x=>22+((x.lactate-lacMin)/(lacMax-lacMin||1))*30));
}
function logEvent(title,text,kind='info'){const row=document.createElement('div');row.className='event-item '+(kind==='danger'?'danger':kind==='warn'?'warn':kind==='ok'?'ok':'');row.innerHTML=`<div class="meta">${fmt(simSeconds())}</div><strong>${title}</strong><div>${text}</div>`;$('eventLog').prepend(row);if((kind==='danger'||kind==='warn')&&soundOn)alarmPulse()}
function renderTimeline(){$('timeline').innerHTML='';if(!history.length){$('timeline').innerHTML='<div class="empty">Sin decisiones registradas.</div>';return}history.slice().reverse().forEach(h=>{const d=document.createElement('div');d.className='titem'+(h.good?'':' bad');d.innerHTML=`<div class="meta">${h.time} · ${h.cat}</div><strong>${h.label}</strong><div>${h.feedback}</div>`;$('timeline').appendChild(d)});$('score').textContent=`${score} pts`}
function applyLocalResponse(id,good){const before={...vital};
  if(id==='oxygen'){vital.spo2=Math.min(97,vital.spo2+6);vital.rr=Math.max(20,vital.rr-2)}
  if(id==='antibiotic'){vital.lactate=Math.max(3.7,+(vital.lactate-.25).toFixed(1));vital.fc=Math.max(100,vital.fc-5)}
  if(id==='fluids'){vital.map+=6;vital.bpSys+=8;vital.bpDia+=4;vital.lactate=Math.max(4,+(vital.lactate-.4).toFixed(1))}
  if(id==='vasopressor'){vital.map+=12;vital.bpSys+=12;vital.bpDia+=5;vital.fc=Math.max(98,vital.fc-8);vital.lactate=Math.max(3.4,+(vital.lactate-.4).toFixed(1))}
  if(id==='source_control'){vital.lactate=Math.max(2.8,+(vital.lactate-.5).toFixed(1))}
  if(['reassess','recheck_map','recheck_lactate'].includes(id))vital.lactate=Math.max(3.4,+(vital.lactate-.1).toFixed(1))
  if(!good){vital.map=Math.max(42,vital.map-5);vital.lactate=Math.min(7.2,+(vital.lactate+.6).toFixed(1));vital.fc+=8}
  return {before,after:{...vital},mapDelta:vital.map-before.map}
}
async function take(id,label){
  ensureAudio();if(paused)return;
  const elapsed=Math.max(.5,(Date.now()-lastAction)/1000);lastAction=Date.now();
  try{
    const res=await app('/api/session/action',{method:'POST',body:JSON.stringify({session_id:sid,action_id:id,elapsed_seconds:elapsed})});
    const q=res.result.good;const local=applyLocalResponse(id,q);Object.assign(vital,res.result.physiology||local.after);
    score+=res.result.score_delta||0;const item={time:fmt(simSeconds()),cat:categoryNames[category],label,good:q,feedback:res.result.feedback||'Acción registrada',mapDelta:local.mapDelta};history.push(item);
    renderVitals();renderTimeline();tone(q?620:270,.11,q?'triangle':'sawtooth',.065);
    showFeedback(res.result.feedback,res.result.observation,q);
    if(q){logEvent('Intervención',res.result.feedback,'ok');say(res.result.feedback,'Equipo')}
    else{logEvent('Deterioro simulado',res.result.feedback,'danger');say('La paciente no mejora. Reevalúa el estado hemodinámico.','Enfermería')}
    if(res.result.case_status)updateCaseStatus(res.result.case_status);
    (res.result.alerts||[]).forEach(al=>{
      logEvent(al.title,al.text,alertKind[al.type]||'warn');
      say(al.text,al.voice_source||'Equipo');
      if(al.type==='deterioration'){alarmPulse();setTimeout(alarmPulse,260)}
    });
  }catch(e){showFeedback('No se pudo registrar la acción',e.message,false)}
}
function showFeedback(title,text,good){let p=document.getElementById('feedbackPanel');if(!p){p=document.createElement('div');p.id='feedbackPanel';p.className='feedback-floating';document.querySelector('.action-card').appendChild(p)}p.className='feedback-floating '+(good?'good':'bad');p.innerHTML=`<strong>${title||'Respuesta del paciente'}</strong><span>${text||''}</span>`;setTimeout(()=>p.remove(),5000)}
async function handleEvent(ev){const key=String(ev.at);if(eventSeen.has(key))return;eventSeen.add(key);try{const r=await app('/api/session/event',{method:'POST',body:JSON.stringify({session_id:sid,event:ev.at})});if(r.text){$('eventTitle').textContent=r.title||'Evento del escenario';$('eventText').textContent=r.text;logEvent(r.title||'Evento',r.text,eventKind[r.type]||'warn');say(r.text,r.voice_source||'Equipo');if(r.patient_voice)say(r.patient_voice,'Paciente')}}catch(e){}}
function tick(){if(paused)return;const s=simSeconds();$('simTimer').textContent=fmt(s);
  if(s>0&&s%8===0&&s!==window._last8){window._last8=s;if(vital.map<65){vital.map=Math.max(44,vital.map-1);vital.lactate=Math.min(8,+(vital.lactate+.1).toFixed(1));renderVitals()}}
  (scenario?.event_schedule||[]).forEach(ev=>{if(s>=ev.at)handleEvent(ev)});
}
function updateCaseStatus(status){
  const el=$('caseStatusTag');if(!el)return;
  const [label,cls]=caseStatusMeta[status]||caseStatusMeta.en_curso;
  el.textContent=label;el.className=cls;
  $('finishBtn').classList.toggle('ready-close',status==='listo_para_cierre');
  $('finishBtn').classList.toggle('escalate',status==='escalamiento_requerido');
}
function updateRoomClock(){const now=new Date();$('roomClock').textContent=now.toLocaleTimeString('es-CO',{hour:'2-digit',minute:'2-digit',hour12:false});setTimeout(updateRoomClock,30000)}
function togglePause(){ensureAudio();if(!paused){paused=true;pauseStarted=Date.now();$('pauseBtn').textContent='▶ Reanudar';$('simState').textContent='● SIMULACIÓN EN PAUSA';$('simState').className='status';tone(350,.08)}else{simPausedAccum+=Date.now()-pauseStarted;paused=false;pauseStarted=null;lastAction=Date.now();$('pauseBtn').textContent='⏸ Pausar';$('simState').textContent='● SIMULACIÓN ACTIVA';$('simState').className='status active';tone(620,.08)}}
async function finish(){ensureAudio();if(paused)togglePause();try{
  const r=await app('/api/session/finish',{method:'POST',body:JSON.stringify({session_id:sid})});
  $('simState').textContent='● SIMULACIÓN FINALIZADA';$('simState').className='status';$('debrief').classList.remove('hidden');
  const outcome=r.debrief.outcome||'Incompleto';const outcomeCls=outcome.toLowerCase();
  $('debriefBody').innerHTML=`<div class="outcome-badge outcome-${outcomeCls}">Desenlace: ${outcome}</div><div class="summary"><div><span>Acciones</span><b>${r.debrief.total_decisions}</b></div><div><span>Puntaje</span><b>${r.debrief.score}</b></div><div><span>Desviaciones</span><b>${r.debrief.deviations}</b></div><div><span>Tiempo</span><b>${fmt(Math.round(r.debrief.elapsed_seconds))}</b></div></div><p class="closure-narrative">${r.debrief.closure_narrative||''}</p><p><strong>Estado final simulado:</strong> ${vital.map>=65?'respuesta hemodinámica parcial':'inestabilidad persistente'}.</p>`;
  $('viewDebrief').classList.remove('hidden');logEvent('Sesión finalizada','Se generó el resumen para debriefing.','ok');
  say(r.debrief.closure_narrative||'La simulación ha finalizado.','Equipo');
  document.querySelectorAll('.action').forEach(b=>b.disabled=true);
  tone(outcome==='Favorable'?880:outcome==='Adverso'?260:520,.12,'sine',.06,.0);tone(outcome==='Favorable'?1040:outcome==='Adverso'?200:460,.14,'sine',.05,.16)
}catch(e){showFeedback('No se pudo finalizar',e.message,false)}}
function setupHotspots(){
  document.querySelectorAll('.room-tool').forEach(b=>b.onclick=()=>{ensureAudio();const el=$(b.dataset.hotspot);el?.animate([{transform:'scale(1)'},{transform:'scale(1.06)'},{transform:'scale(1)'}],{duration:500});tone(520,.05);});
  [$('patientHotspot'),$('monitorHotspot'),$('ivHotspot'),$('cartHotspot'),$('oxygenHotspot'),$('suctionHotspot'),$('ventilatorHotspot')].forEach(el=>el?.addEventListener('click',()=>{ensureAudio();tone(480,.05)}));
}
document.querySelectorAll('.action-tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.action-tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');category=b.dataset.cat;renderActions();});
$('pauseBtn').onclick=togglePause;$('finishBtn').onclick=finish;
$('soundBtn').onclick=()=>{$('audioPanel').classList.toggle('hidden');ensureAudio();$('audioEnable').textContent='▶ Activar sonido';}
$('audioEnable').onclick=()=>{ensureAudio();soundOn=true;setMasterGain();$('soundBtn').textContent='🔊 Audio';$('soundBtn').setAttribute('aria-pressed','true');$('audioEnable').textContent='✓ Sonido activado';monitorBeep();startHeartLoop();startAmbient();updateAlarm()};
$('volumeRange').oninput=()=>{ensureAudio();setMasterGain()};
$('monitorSound').onchange=()=>{ensureAudio();startHeartLoop()};
$('ambientSound').onchange=()=>{ensureAudio();$('ambientSound').checked?startAmbient():stopAmbient()};
$('alarmSound').onchange=()=>{ensureAudio();updateAlarm()};
$('voiceSound').onchange=e=>{voiceEnabled=e.target.checked};
$('toggleInfo').onclick=()=>{const e=$('infoList');const hide=e.classList.contains('hidden');e.classList.toggle('hidden',!hide);$('toggleInfo').textContent=hide?'Ocultar':'Mostrar'};
$('clearEvent').onclick=()=>$('eventLog').innerHTML='';
$('clearVoice').onclick=()=>$('voiceLog').innerHTML='';
$('viewDebrief').onclick=()=>$('debrief').scrollIntoView({behavior:'smooth'});
window.addEventListener('load',()=>start().catch(e=>showFeedback('Error de inicio',e.message,false)));
