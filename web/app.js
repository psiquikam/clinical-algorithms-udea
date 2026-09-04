let scenario=null,sid=null,category='observe',soundOn=true,paused=false;
let simMode='standard',subtitlesOn=true,pausasPermitidas=true;
let simStart=Date.now(),pauseStarted=null,simPausedAccum=0,lastAction=Date.now(),score=0,history=[],eventSeen=new Set();
let audioCtx=null,masterGain=null,ambientNode=null,ambientGain=null,heartTimer=null,alarmTimer=null,voiceEnabled=true;
let audioUnlocked=false,alarmVoiceTurn=0;
let arrestActive=false,caseStabilized=false,caseLocked=false,flatlineTimer=null;
const ECG_NORMAL_POINTS="0,72 20,72 24,72 30,30 36,92 44,72 62,72 72,72 78,40 84,86 92,72 112,72 120,72 126,32 132,92 140,72 160,72 168,72 174,36 180,88 188,72 208,72 216,72 222,32 228,92 236,72 260,72";
const categoryNames={observe:'Observación',investigate:'Información',intervene:'Intervención',reassess:'Reevaluación',emergency:'Emergencia'};
const eventKind={nursing:'warn',labs:'info',clinical:'warn',deterioration:'danger',closure:'ok',monitor:'warn'};
const caseStatusMeta={en_curso:['Caso en curso',''],listo_para_cierre:['Listo para cierre','ready'],escalamiento_requerido:['Requiere escalamiento','critical'],paro_cardiorrespiratorio:['Paro cardiorrespiratorio','critical'],desenlace_adverso:['Desenlace adverso','critical']};
const alertKind={encouragement:'ok',consciousness:'warn',deterioration:'danger',closure:'ok',deviation:'danger',arrest:'danger',rosc:'ok',case_end:'danger'};
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
function unlockAudio(){
  ensureAudio();setMasterGain();
  const hint=$('audioUnlockHint');if(hint&&!audioUnlocked)hint.classList.add('hidden');
  audioUnlocked=true;
  if(soundOn){
    if($('monitorSound').checked)startHeartLoop();
    if($('ambientSound').checked)startAmbient();
    updateAlarm();
  }
  processVoiceQueue();
}
document.addEventListener('pointerdown',unlockAudio,{once:true});
document.addEventListener('keydown',unlockAudio,{once:true});
function tone(freq=520,dur=.08,type='sine',gain=.08,when=0){
  if(!audioCtx||!soundOn)return;
  const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type=type;o.frequency.value=freq;o.connect(g);g.connect(masterGain);
  const t=audioCtx.currentTime+when;g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(Math.max(.001,gain),t+.01);g.gain.exponentialRampToValueAtTime(.0001,t+dur);o.start(t);o.stop(t+dur+.03);
}
function monitorBeep(){
  if(!$('monitorSound').checked||!soundOn||arrestActive)return;
  // El tono se vuelve más agudo y urgente con taquicardia marcada, y más
  // grave con bradicardia — refuerzo sonoro real de la gravedad, no solo
  // un pitido plano igual pase lo que pase.
  const fc=vital.fc;
  const freq=fc>140?880:fc>120?780:fc<50?480:vital.spo2<90?760:620;
  const gain=fc>120||vital.spo2<90?.095:.075;
  tone(freq,.055,'sine',gain);
}
function startFlatlineTone(){
  stopFlatlineTone();
  flatlineTimer=setInterval(()=>{if(soundOn&&$('monitorSound').checked)tone(920,.85,'sine',.05)},900);
}
function stopFlatlineTone(){clearInterval(flatlineTimer);flatlineTimer=null}
function alarmPulse(){
  if(!$('alarmSound').checked||!soundOn)return;
  tone(780,.11,'square',.085);tone(590,.11,'square',.07,.14);
}
function startHeartLoop(){
  clearTimeout(heartTimer);
  if(arrestActive)return;
  const bpm=Math.max(45,Math.min(180,vital.fc));
  const interval=60000/bpm;
  heartTimer=setTimeout(()=>{monitorBeep();flashMonitor();startHeartLoop()},interval);
}
function flashMonitor(){const m=document.querySelector('.monitor-screen');if(!m)return;m.classList.remove('flash');void m.offsetWidth;m.classList.add('flash')}
function updateAlarm(){
  if(arrestActive||caseStabilized){clearInterval(alarmTimer);alarmTimer=null;$('alarmLight').classList.add('hidden');return}
  const bad=vital.map<65||vital.spo2<90;
  $('alarmLight').classList.toggle('hidden',!bad);
  $('alarmLabel').textContent=vital.map<65?'PAM baja':vital.spo2<90?'SpO₂ baja':'Alerta';
  if(bad&&soundOn){if(!alarmTimer) alarmTimer=setInterval(alarmPulse,4200)} else {clearInterval(alarmTimer);alarmTimer=null}
  if(bad&&voiceEnabled&&Date.now()-lastAlarmSpoken>18000){
    lastAlarmSpoken=Date.now();
    const isMap=vital.map<65;
    const lines=isMap?[
      {t:'Alarma. Presión arterial baja.',s:'Monitor'},
      {t:'Doctor, la presión continúa baja.',s:'Enfermería'},
      {t:'Está respondiendo cada vez menos.',s:'Enfermería'},
    ]:[
      {t:'Alarma. Saturación de oxígeno baja.',s:'Monitor'},
      {t:'Doctor, la saturación sigue baja.',s:'Enfermería'},
      {t:'La paciente respira con más dificultad.',s:'Enfermería'},
    ];
    const line=lines[alarmVoiceTurn%lines.length];alarmVoiceTurn++;
    say(line.t,line.s);
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
  if(subtitlesOn){
    $('voiceBubble').classList.remove('hidden');$('voiceBubble').dataset.source=source;$('voiceBubble').classList.remove('pulse');void $('voiceBubble').offsetWidth;$('voiceBubble').classList.add('pulse');
    $('voiceSource').textContent=source;$('voiceText').textContent=text;
  }
  logVoice(source,text);
  const endTurn=()=>{speaking=false;$('voiceBubble').classList.add('hidden');processVoiceQueue()};
  if(voiceEnabled&&'speechSynthesis' in window){
    // No se espera un gesto previo del usuario para narrar: la mayoría de
    // navegadores permite síntesis de voz desde el inicio de la simulación.
    // Si el navegador la bloquea por política de autoplay, onerror libera el turno.
    try{
      const profile=voiceProfiles[source]||{rate:.95,pitch:1};
      const u=new SpeechSynthesisUtterance(text);
      u.lang='es-CO';u.rate=profile.rate;u.pitch=profile.pitch;u.volume=(+$('volumeRange').value/100);
      u.onend=endTurn;u.onerror=endTurn;
      window.speechSynthesis.speak(u);
    }catch(e){endTurn()}
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
  say('Tenemos una paciente de 65 años, con fiebre, hipotensión y alteración del estado mental.','Equipo');
  historyVitals.push({map:vital.map,lactate:vital.lactate});
  setInterval(tick,500);setupHotspots();
  updateAlarm();startHeartLoop();updateRoomClock();
  lastCoachAt=Date.now();setInterval(pollCoach,coachIntervalMs());
}
let lastCoachAt=0;
function coachIntervalMs(){
  // Frecuencia de sondeo del servidor: sincroniza signos vitales en vivo y
  // el reloj crítico incluso si el usuario no hace nada. El mensaje del
  // preceptor tiene su propio enfriamiento interno en el backend, así que
  // sondear seguido no genera más charla — solo un monitor más "vivo".
  return simMode==='prep'?10000:simMode==='advanced'?15000:12000;
}
async function pollCoach(){
  if(paused||!sid||caseLocked)return;
  const elapsed=Math.max(1,(Date.now()-lastCoachAt)/1000);lastCoachAt=Date.now();
  try{
    const r=await app('/api/session/coach',{method:'POST',body:JSON.stringify({session_id:sid,elapsed_seconds:elapsed})});
    if(r.physiology)Object.assign(vital,r.physiology);
    if(r.message&&r.message.text){
      logEvent('Orientación',r.message.text,'ok');
      say(r.message.text,r.message.voice_source||'Equipo');
    }
    setArrestMode(!!r.arrest);
    renderVitals();renderTimeline();
    handleAlertsList(r.alerts);
    if(r.case_status)updateCaseStatus(r.case_status);
    if(r.case_status==='desenlace_adverso')declareCaseEnd();
  }catch(e){/* orientación proactiva es opcional; se ignora si falla */}
}
function handleAlertsList(alerts){
  (alerts||[]).forEach(al=>{
    logEvent(al.title,al.text,alertKind[al.type]||'warn');
    say(al.text,al.voice_source||'Equipo');
    if(al.type==='deterioration'){alarmPulse();setTimeout(alarmPulse,260)}
    if(al.type==='arrest'){tone(920,.5,'sine',.08)}
    if(al.type==='closure')markCaseStabilized();
    if(al.type==='case_end')declareCaseEnd();
  });
}
function renderScenario(){$('nodeLabel').textContent='Inicio · evaluación inicial'}
function renderInfo(){const p=scenario.patient;$('infoList').innerHTML='';[['Alergia',p.alergias],['Leucocitos',p.leucocitos+' /µL'],['Creatinina',p.creatinina+' mg/dL'],['Plaquetas',p.plaquetas+' ×10³/µL'],['PaFi',p.pafi],['Foco',p.foco]].forEach(([k,v])=>{const d=document.createElement('div');d.className='info-row';d.innerHTML=`<span>${k}</span><strong>${v}</strong>`;$('infoList').appendChild(d)})}
function renderActions(){const list=scenario.actions[category]||[];$('actions').innerHTML='';list.forEach(item=>{const [id,label,desc]=item;const b=document.createElement('button');b.className='action';b.innerHTML=`<strong>${label}</strong><small>${desc}</small>`;b.addEventListener('click',()=>take(id,label));$('actions').appendChild(b)})}
function renderVitals(){
  $('fc').textContent=arrestActive?'0':Math.round(vital.fc);$('bp').textContent=arrestActive?'—/—':`${Math.round(vital.bpSys)}/${Math.round(vital.bpDia)}`;
  $('spo2').textContent=Math.round(vital.spo2);$('rr').textContent=Math.round(vital.rr);$('map').textContent=Math.round(vital.map);$('lactate').textContent=vital.lactate.toFixed(1);
  $('sceneFc').textContent=arrestActive?'0':Math.round(vital.fc);$('ventRate').textContent=Math.round(Math.max(12,vital.rr-10));
  const unstable=vital.map<65||vital.spo2<90;const partial=!unstable&&vital.lactate>2;
  if(arrestActive){
    $('severityTag').textContent='PARO';$('severityTag').className='critical';
    $('patientState').textContent='Sin respuesta · sin pulso palpable';$('respState').textContent='Sin esfuerzo respiratorio espontáneo';
  }else if(caseStabilized){
    $('severityTag').textContent='ESTABILIZADA';$('severityTag').className='partial';
    $('patientState').textContent='Alerta y orientada · responde apropiadamente';$('respState').textContent='Respiración regular, sin soporte adicional';
  }else{
    $('severityTag').textContent=unstable?'CRÍTICO':partial?'RESPUESTA PARCIAL':'ESTABILIZACIÓN';
    $('severityTag').className=unstable?'critical':'partial';
    $('patientState').textContent=vital.map<55?'Somnolienta · respuesta disminuida':vital.map<65?'Somnolienta · responde a la voz':'Más alerta · responde mejor';
    $('respState').textContent=vital.spo2<90?'Respiración comprometida · hipoxemia':vital.rr>22?'Respiración rápida':'Respiración más regular';
  }
  $('hemoTag').textContent=arrestActive?'Sin pulso':vital.map<65?'Hipotensión':'PAM en mejoría';
  $('perfTag').textContent=arrestActive?'Sin perfusión':vital.lactate>4?'Hipoperfusión':'Perfusión en recuperación';
  $('stateDot').classList.toggle('improving',!unstable&&!arrestActive);
  $('patientBody').classList.toggle('deteriorating',unstable&&!arrestActive&&!caseStabilized);
  $('patientBody').classList.toggle('improving',!unstable&&!arrestActive&&!caseStabilized);
  $('patientBody').classList.toggle('arrest',arrestActive);
  $('patientBody').classList.toggle('stabilized',caseStabilized&&!arrestActive);
  // La animación del ECG se acelera o enlentece con la frecuencia real.
  const poly=$('ecgWave');
  if(poly&&!arrestActive)poly.style.animationDuration=(Math.max(.55,Math.min(2.2,60/Math.max(35,vital.fc)))).toFixed(2)+'s';
  updateAlarm();
  historyVitals.push({map:vital.map,lactate:vital.lactate});drawTrends();
}
function setEcgFlatline(flat){
  const poly=$('ecgWave');if(!poly)return;
  const screen=document.querySelector('.monitor-screen');
  if(flat){poly.setAttribute('points','0,72 260,72');poly.style.animation='none';screen?.classList.add('arrest');screen?.classList.remove('stabilized')}
  else{poly.setAttribute('points',ECG_NORMAL_POINTS);poly.style.animation='';screen?.classList.remove('arrest')}
}
function setArrestMode(active){
  if(active===arrestActive)return;
  arrestActive=active;
  $('arrestBanner').classList.toggle('hidden',!active);
  $('emergencyTab').classList.toggle('hidden',!active);
  setEcgFlatline(active);
  if(active){
    clearTimeout(heartTimer);clearInterval(alarmTimer);alarmTimer=null;
    startFlatlineTone();
    document.querySelectorAll('.action-tab').forEach(t=>t.classList.remove('active'));
    $('emergencyTab').classList.add('active');
    category='emergency';renderActions();
  }else{
    stopFlatlineTone();
    document.querySelectorAll('.action-tab').forEach(t=>t.classList.remove('active'));
    $('emergencyTab').classList.remove('active');
    const intervTab=document.querySelector('.action-tab[data-cat="intervene"]');
    intervTab?.classList.add('active');category='intervene';renderActions();
    startHeartLoop();
  }
  renderVitals();
}
function markCaseStabilized(){
  if(caseStabilized)return;
  caseStabilized=true;clearInterval(alarmTimer);alarmTimer=null;$('alarmLight').classList.add('hidden');
  document.querySelector('.monitor-screen')?.classList.add('stabilized');
  renderVitals();
  tone(880,.14,'sine',.07,0);tone(1180,.18,'sine',.06,.16);
}
function declareCaseEnd(){
  if(caseLocked)return;caseLocked=true;
  document.querySelectorAll('.action').forEach(b=>b.disabled=true);
  clearInterval(alarmTimer);alarmTimer=null;stopFlatlineTone();
  setTimeout(()=>{if(!$('debrief')||$('debrief').classList.contains('hidden'))finish()},1800);
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
  unlockAudio();if(paused||caseLocked)return;
  const elapsed=Math.max(.5,(Date.now()-lastAction)/1000);lastAction=Date.now();
  try{
    const res=await app('/api/session/action',{method:'POST',body:JSON.stringify({session_id:sid,action_id:id,elapsed_seconds:elapsed})});
    const q=res.result.good;const local=applyLocalResponse(id,q);Object.assign(vital,res.result.physiology||local.after);
    score+=res.result.score_delta||0;const item={time:fmt(simSeconds()),cat:categoryNames[category],label,good:q,feedback:res.result.feedback||'Acción registrada',mapDelta:local.mapDelta};history.push(item);
    setArrestMode(!!res.result.arrest);
    renderVitals();renderTimeline();tone(q?620:270,.11,q?'triangle':'sawtooth',.065);
    showFeedback(res.result.feedback,res.result.observation,q);
    if(q){logEvent('Intervención',res.result.feedback,'ok');say(res.result.feedback,'Equipo')}
    else{logEvent('No es correcto aún',res.result.feedback,'danger');say(res.result.feedback,'Enfermería')}
    if(res.result.case_status)updateCaseStatus(res.result.case_status);
    handleAlertsList(res.result.alerts);
    if(res.result.case_status==='desenlace_adverso')declareCaseEnd();
  }catch(e){showFeedback('No se pudo registrar la acción',e.message,false)}
}
function showFeedback(title,text,good){let p=document.getElementById('feedbackPanel');if(!p){p=document.createElement('div');p.id='feedbackPanel';p.className='feedback-floating';document.querySelector('.action-card').appendChild(p)}p.className='feedback-floating '+(good?'good':'bad');p.innerHTML=`<strong>${title||'Respuesta del paciente'}</strong><span>${text||''}</span>`;setTimeout(()=>p.remove(),5000)}
async function handleEvent(ev){const key=String(ev.at);if(eventSeen.has(key))return;eventSeen.add(key);try{const r=await app('/api/session/event',{method:'POST',body:JSON.stringify({session_id:sid,event:ev.at})});if(r.text){$('eventTitle').textContent=r.title||'Evento del escenario';$('eventText').textContent=r.text;logEvent(r.title||'Evento',r.text,eventKind[r.type]||'warn');say(r.text,r.voice_source||'Equipo');if(r.patient_voice)say(r.patient_voice,'Paciente')}}catch(e){}}
function tick(){if(paused||caseLocked)return;const s=simSeconds();$('simTimer').textContent=fmt(s);
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
function togglePause(){unlockAudio();if(!paused){paused=true;pauseStarted=Date.now();$('pauseBtn').textContent='▶ Reanudar';$('simState').textContent='● SIMULACIÓN EN PAUSA';$('simState').className='status';tone(350,.08)}else{simPausedAccum+=Date.now()-pauseStarted;paused=false;pauseStarted=null;lastAction=Date.now();$('pauseBtn').textContent='⏸ Pausar';$('simState').textContent='● SIMULACIÓN ACTIVA';$('simState').className='status active';tone(620,.08)}}
async function finish(){unlockAudio();if(paused)togglePause();caseLocked=true;try{
  const r=await app('/api/session/finish',{method:'POST',body:JSON.stringify({session_id:sid})});
  $('simState').textContent='● SIMULACIÓN FINALIZADA';$('simState').className='status';$('debrief').classList.remove('hidden');
  const outcome=r.debrief.outcome||'Incompleto';const outcomeCls=outcome.toLowerCase();
  const bundle=r.debrief.bundle_status||{};
  const bundleRow=(label,done)=>`<div class="bundle-item ${done?'done':'missed'}"><span>${done?'✔':'✘'}</span>${label}</div>`;
  const bundleHtml=`<div class="bundle-check">
    ${bundleRow('Acceso IV',bundle.iv_access)}
    ${bundleRow('Hemocultivos',bundle.cultures_done)}
    ${bundleRow('Antibiótico',bundle.antibiotic_given)}
    ${bundleRow('Cristaloides ('+(bundle.fluids_ml||0)+' mL)',(bundle.fluids_ml||0)>0)}
    ${bundleRow('Vasopresor',bundle.vasopressor_started)}
    ${bundleRow('Control del foco',bundle.source_control_done)}
  </div>`;
  const deviations=r.debrief.protocol_deviations||[];
  const deviationsHtml=deviations.length?`<div class="deviation-list"><strong>Desviaciones del protocolo (${deviations.length}):</strong><ul>${deviations.map(d=>`<li>${d}</li>`).join('')}</ul></div>`:'<div class="deviation-list ok">Sin desviaciones registradas del protocolo.</div>';
  const arrestHtml=r.debrief.arrest_occurred?`<div class="deviation-list ${r.debrief.rosc_achieved?'ok':''}"><strong>Episodio de paro cardiorrespiratorio:</strong> ${r.debrief.rosc_achieved?`se logró retorno de circulación espontánea tras ${r.debrief.epinephrine_doses} dosis de adrenalina y RCP.`:'no se logró retorno de circulación espontánea.'}</div>`:'';
  const finalStateText=r.debrief.case_status==='desenlace_adverso'?'paro cardiorrespiratorio sin retorno de circulación':r.debrief.case_status==='listo_para_cierre'?'estabilización sostenida':vital.map>=65?'respuesta hemodinámica parcial':'inestabilidad persistente';
  $('debriefBody').innerHTML=`<div class="outcome-badge outcome-${outcomeCls}">Desenlace: ${outcome}</div><div class="summary"><div><span>Acciones</span><b>${r.debrief.total_decisions}</b></div><div><span>Puntaje</span><b>${r.debrief.score}</b></div><div><span>Desviaciones</span><b>${r.debrief.deviations}</b></div><div><span>Tiempo</span><b>${fmt(Math.round(r.debrief.elapsed_seconds))}</b></div></div><p class="closure-narrative">${r.debrief.closure_narrative||''}</p>${bundleHtml}${arrestHtml}${deviationsHtml}<p><strong>Estado final simulado:</strong> ${finalStateText}.</p>`;
  $('viewDebrief').classList.remove('hidden');logEvent('Sesión finalizada','Se generó el resumen para debriefing.','ok');
  say(r.debrief.closure_narrative||'La simulación ha finalizado.','Equipo');
  document.querySelectorAll('.action').forEach(b=>b.disabled=true);
  clearInterval(alarmTimer);stopFlatlineTone();
  tone(outcome==='Favorable'?880:outcome==='Adverso'?260:520,.12,'sine',.06,.0);tone(outcome==='Favorable'?1040:outcome==='Adverso'?200:460,.14,'sine',.05,.16)
}catch(e){showFeedback('No se pudo finalizar',e.message,false)}}
function setupHotspots(){
  document.querySelectorAll('.room-tool').forEach(b=>b.onclick=()=>{unlockAudio();const el=$(b.dataset.hotspot);el?.animate([{transform:'scale(1)'},{transform:'scale(1.06)'},{transform:'scale(1)'}],{duration:500});tone(520,.05);});
  [$('patientHotspot'),$('monitorHotspot'),$('ivHotspot'),$('cartHotspot'),$('oxygenHotspot'),$('suctionHotspot'),$('ventilatorHotspot')].forEach(el=>el?.addEventListener('click',()=>{unlockAudio();tone(480,.05)}));
}
document.querySelectorAll('.action-tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.action-tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');category=b.dataset.cat;renderActions();});
$('pauseBtn').onclick=togglePause;$('finishBtn').onclick=finish;
$('soundBtn').onclick=()=>{$('audioPanel').classList.toggle('hidden');unlockAudio();};
function setMuteState(muted){
  soundOn=!muted;voiceEnabled=!muted&&$('voiceSound').checked;
  $('soundBtn').textContent=muted?'🔇 Silenciado':'🔊 Audio activo';
  $('soundBtn').setAttribute('aria-pressed',String(!muted));
  $('audioEnable').textContent=muted?'🔊 Reactivar sonido':'🔇 Silenciar todo';
  if(muted){clearInterval(alarmTimer);alarmTimer=null;stopAmbient();window.speechSynthesis?.cancel();}
  else{unlockAudio();}
}
$('audioEnable').onclick=()=>setMuteState(soundOn);
$('volumeRange').oninput=()=>{unlockAudio();setMasterGain()};
$('monitorSound').onchange=()=>{unlockAudio();$('monitorSound').checked?startHeartLoop():clearTimeout(heartTimer)};
$('ambientSound').onchange=()=>{unlockAudio();$('ambientSound').checked?startAmbient():stopAmbient()};
$('alarmSound').onchange=()=>{unlockAudio();updateAlarm()};
$('voiceSound').onchange=e=>{voiceEnabled=soundOn&&e.target.checked};
$('toggleInfo').onclick=()=>{const e=$('infoList');const hide=e.classList.contains('hidden');e.classList.toggle('hidden',!hide);$('toggleInfo').textContent=hide?'Ocultar':'Mostrar'};
$('clearEvent').onclick=()=>$('eventLog').innerHTML='';
$('clearVoice').onclick=()=>$('voiceLog').innerHTML='';
$('viewDebrief').onclick=()=>$('debrief').scrollIntoView({behavior:'smooth'});
/* ── Bienvenida / Onboarding ── */
function showOnbStep(n){
  document.querySelectorAll('.onb-step').forEach(s=>s.classList.toggle('hidden',s.dataset.step!==String(n)));
}
$('onbToStep2').onclick=()=>showOnbStep(2);
$('onbBack2').onclick=()=>showOnbStep(1);
$('onbAccept').onchange=e=>{$('onbToStep3').disabled=!e.target.checked};
$('onbToStep3').onclick=()=>showOnbStep(3);
$('onbBack3').onclick=()=>showOnbStep(2);
function applyOnboardingConfigAndEnter(useDefaults){
  if(!useDefaults){
    $('monitorSound').checked=$('cfgMonitor').checked;
    $('ambientSound').checked=$('cfgAmbient').checked;
    $('alarmSound').checked=$('cfgAlarm').checked;
    $('voiceSound').checked=$('cfgVoice').checked;
    soundOn=$('cfgMonitor').checked||$('cfgAmbient').checked||$('cfgAlarm').checked||$('cfgVoice').checked;
    voiceEnabled=$('cfgVoice').checked;
    subtitlesOn=$('cfgSubtitles').checked;
    pausasPermitidas=$('cfgPause').checked;
    document.body.classList.toggle('high-contrast',$('cfgContrast').checked);
    document.body.classList.toggle('text-lg',$('cfgTextLg').checked);
    const modeInput=document.querySelector('input[name="cfgMode"]:checked');
    simMode=modeInput?modeInput.value:'standard';
  }
  if(!pausasPermitidas){$('pauseBtn').classList.add('hidden')}
  $('onboarding').classList.add('hidden');
  start().catch(e=>showFeedback('Error de inicio',e.message,false));
}
$('onbSkip').onclick=()=>applyOnboardingConfigAndEnter(true);
$('onbFinish').onclick=()=>applyOnboardingConfigAndEnter(false);
