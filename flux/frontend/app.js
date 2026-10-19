'use strict';
const $ = selector => document.querySelector(selector);
const icons = {
  plus:'<path d="M12 5v14M5 12h14"/>', chat:'<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-3 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>', memory:'<rect x="5" y="5" width="14" height="14" rx="4"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/><circle cx="12" cy="12" r="2"/>',
  mic:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8"/>', wave:'<path d="M3 10v4m4-8v12m5-16v20m5-16v12m4-8v4"/>',
  settings:'<path d="m9 3 1-2h4l1 2 3 2 3 1v4l-2 2 2 2v4l-3 1-3 2-1 2h-4l-1-2-3-2-3-1v-4l2-2-2-2V6l3-1Z" transform="translate(1 1) scale(.85)"/><circle cx="12" cy="12" r="3"/>',
  arrow:'<path d="M12 19V5m-6 6 6-6 6 6"/>', spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>', plan:'<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 2v4m6-4v4M9 11h6m-6 4h4"/>',
  edit:'<path d="m14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 15Z"/>', trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>'
};
function icon(name) {
  const span=document.createElement('span');
  // Only hard-coded icon definitions enter HTML. User/model text always uses DOM text nodes.
  span.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.chat}</svg>`;
  return span;
}
document.querySelectorAll('[data-icon]').forEach(e=>e.replaceChildren(icon(e.dataset.icon)));
document.querySelectorAll('.orb,.brand-orb').forEach(root=>FluxOrb.mount(root));
let backend=null, state=null, pending=null, inFlight=null, menuSession=null, modalAction=null, cancelAction=null;
function send(action, values={}) { if(backend) backend.dispatch(JSON.stringify({action,...values})); }
function node(tag, className, text) {const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;}
function actionButton(text, callback, className='') {const e=node('button',className,text);e.type='button';e.onclick=callback;return e;}
function date(text) {const d=new Date(text.replace(' ','T')+'Z');return Number.isNaN(d.getTime())?'Saved locally':d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});}

function inline(parent,text) {
  // Small, safe Markdown subset: emphasis and code. No HTML, external images or executable links.
  const pieces=text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  for(const piece of pieces){if(piece.startsWith('`')&&piece.endsWith('`'))parent.append(node('code','',piece.slice(1,-1)));else if(piece.startsWith('**')&&piece.endsWith('**'))parent.append(node('strong','',piece.slice(2,-2)));else parent.append(document.createTextNode(piece));}
}
function markdown(text) {
  const root=node('div','message-content');let code=null,list=null;
  for(const line of text.split('\n')) {
    if(line.startsWith('```')){if(code){root.append(code);code=null;}else{code=node('pre');code.append(node('code'));}list=null;continue;}
    if(code){code.firstChild.append(document.createTextNode(line+'\n'));continue;}
    const heading=line.match(/^(#{1,6})\s+(.*)/);const bullet=line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if(heading){const h=node('h'+Math.min(heading[1].length+1,4));inline(h,heading[2]);root.append(h);list=null;}
    else if(bullet){const type=/^\s*\d/.test(line)?'ol':'ul';if(!list||list.tagName.toLowerCase()!==type){list=node(type);root.append(list);}const li=node('li');inline(li,bullet[1]);list.append(li);}
    else {list=null;if(line){const p=node('p');inline(p,line);root.append(p);}}
  }
  if(code)root.append(code);return root;
}
function message(role,text,avatar=null) {
  const card=node('article','message '+role);const header=node('div','message-header');
  card.dataset.role=role;card.messageText=text;
  if(role==='assistant'){if(!avatar){avatar=node('img','message-avatar');avatar.src='../assets/flux-orb.png';avatar.alt='';}header.append(avatar);}
  header.append(node('span','',role==='user'?'YOU':'FLUX'));
  header.append(actionButton('Copy',()=>send('copy',{text}),'copy'));
  card.append(header);
  if(role==='user'){const body=node('div','message-content');body.append(node('p','',text));card.append(body);}else card.append(markdown(text));
  return card;
}
function renderSessions() {
  const target=$('#sessions');target.replaceChildren();
  const query=$('#search').value.toLocaleLowerCase();
  const sessions=state.sessions.filter(s=>s.title.toLocaleLowerCase().includes(query));
  for(const session of sessions){
    const row=node('div','session-row'+(state.session===session.id?' selected':''));
    const select=actionButton('',()=>send('load',{id:session.id}),'session-select');select.append(node('span','',session.title));select.title=session.title+'\nCreated '+date(session.created)+' · Updated '+date(session.updated);select.disabled=state.busy||state.recording;
    const menu=actionButton('•••',event=>{event.stopPropagation();menuSession=session;const rect=menu.getBoundingClientRect();const popup=$('#conversation-menu');popup.hidden=false;popup.style.left=Math.min(rect.left,window.innerWidth-160)+'px';popup.style.top=Math.min(rect.bottom+4,window.innerHeight-110)+'px';},'session-menu-button');
    menu.setAttribute('aria-label','Manage '+session.title);menu.disabled=state.busy||state.recording;row.append(select,menu);target.append(row);
  }
  if(!sessions.length)target.append(node('p','empty-sessions',query?'No conversations found.':'Your conversations will appear here. Start with a thought.'));
}
function renderMemories() {
  const target=$('#memory-list');target.replaceChildren();
  for(const memory of state.memories){
    const card=node('article','memory-card');card.append(node('span','category',memory.category),node('p','',memory.content));
    const footer=node('div','memory-card-footer');const timestamp=node('small','',date(memory.created));timestamp.title='Updated '+date(memory.updated);footer.append(timestamp);
    const edit=actionButton('',()=>memoryDialog(memory));edit.append(icon('edit'));edit.title='Edit memory';edit.setAttribute('aria-label','Edit '+memory.content);
    const remove=actionButton('',()=>send('requestDelete',{kind:'memory',id:memory.id}));remove.append(icon('trash'));remove.title='Delete memory';remove.setAttribute('aria-label','Delete '+memory.content);
    edit.disabled=remove.disabled=state.busy||state.recording;footer.append(edit,remove);card.append(footer);target.append(card);
  }
  if(!state.memories.length){const empty=node('div','empty-memory');empty.append(icon('memory'),node('h3','','A little more you, over time.'),node('p','','Tell Flux “My favorite programming language is Python.”'),node('p','','Or add a memory yourself. It will be here whenever you return.'));target.append(empty);}
  $('#memory-total').textContent=state.memories.length+' '+(state.memories.length===1?'memory':'memories');
  $('#clear-memories').disabled=!state.memories.length||state.busy||state.recording;
}
let renderedSession, cards=[], waiting=null, followLatest=true;
function dispose(element){
  element.querySelectorAll('.orb-live').forEach(root=>FluxOrb.release(root));
  element.remove();
}
function scrollLatest(smooth=true,anchor=null){
  const scroller=$('#chat-scroll');
  requestAnimationFrame(()=>{
    const softened=state.reducedMotion||matchMedia('(prefers-reduced-motion: reduce)').matches;
    // A long answer should begin at its heading, not jump past everything to its end.
    const top=anchor&&anchor.offsetHeight>scroller.clientHeight*.65
      ? anchor.getBoundingClientRect().top-scroller.getBoundingClientRect().top+scroller.scrollTop-18
      : scroller.scrollHeight;
    scroller.scrollTo({top,behavior:smooth&&!softened?'smooth':'instant'});
  });
}
$('#chat-scroll').addEventListener('scroll',()=>{
  const scroller=$('#chat-scroll');
  $('#jump-latest').hidden=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<100;
});
$('#chat-scroll').addEventListener('wheel',event=>{if(event.deltaY<0)followLatest=false;else{const s=$('#chat-scroll');if(s.scrollHeight-s.scrollTop-s.clientHeight<130)followLatest=true;}},{passive:true});
$('#chat-scroll').addEventListener('pointerdown',()=>{followLatest=false;});
$('#jump-latest').onclick=()=>{followLatest=true;scrollLatest();};
function renderMessages(){
  const target=$('#messages');
  const adoptingDraft=renderedSession===null&&!!pending&&state.session!==null;
  const switched=renderedSession!==state.session&&!adoptingDraft;
  if(switched){cards.forEach(dispose);cards=[];if(waiting){dispose(waiting);waiting=null;}followLatest=true;}
  renderedSession=state.session;
  $('#welcome').hidden=state.messages.length>0||!!pending;
  const desired=[...state.messages];
  if(pending)desired.push({role:'user',content:pending.text});
  let inserted=null;
  desired.forEach((m,index)=>{
    if(cards[index]?.dataset.role===m.role&&cards[index].messageText===m.content)return;
    if(cards[index]){cards.slice(index).forEach(dispose);cards.length=index;}
    // Move the existing thinking orb into the reply instead of destroying/restarting it.
    const avatar=m.role==='assistant'&&waiting?waiting.querySelector('.orb-live'):null;
    const card=message(m.role,m.content,avatar);
    if(avatar){waiting.remove();waiting=null;}
    if(!switched){card.classList.add('message-enter');if(m.role==='assistant'){card.querySelector('.message-content').classList.add('answer-enter');FluxOrb.respond();}}
    target.append(card);cards.push(card);inserted=card;
  });
  while(cards.length>desired.length)dispose(cards.pop());
  if(pending?.phase!=='failed')cards.forEach(card=>card.querySelector('.message-failure')?.remove());
  if(pending?.phase==='sending'){
    if(!waiting){waiting=node('div','thinking-card');waiting.append(FluxOrb.create('orb-small'),node('span','thinking-label','Flux'));target.append(waiting);}
    // Historical response avatars stay light; the current presence is always animated.
    cards.forEach(card=>card.querySelectorAll('.orb-live').forEach(root=>{const img=node('img','message-avatar');img.src='../assets/flux-orb.png';img.alt='';FluxOrb.release(root);root.replaceWith(img);}));
  }else if(waiting){dispose(waiting);waiting=null;}
  if(pending?.phase==='failed'){
    const card=cards[cards.length-1];
    if(!card.querySelector('.message-failure')){const note=node('div','message-failure');note.append(node('span','','Not sent'),actionButton('Retry',()=>sendMessage(pending?.text,true)));card.append(note);}
  }
  if(switched)scrollLatest(false);
  else if(inserted&&followLatest)scrollLatest(true,inserted.dataset.role==='assistant'?inserted:null);
  const answer=[...state.messages].reverse().find(m=>m.role==='assistant');$('#voice-answer').hidden=!answer;$('#voice-answer').textContent=answer?answer.content:'';
}
function renderStatus(){
  document.body.dataset.state=state.state;
  FluxOrb.setState(state.state);
  FluxOrb.reduce(state.reducedMotion);
  if(!state.recording)FluxOrb.setLevel(0);
  $('#status').textContent=state.status;
  const disabled=state.busy||state.recording||!!inFlight;
  document.querySelectorAll('[data-page],#new-chat,#mode,#add-memory,#auto-memory,#reduce-motion').forEach(e=>e.disabled=disabled);
  // Keep the empty editor ready for the next draft while the single request runs.
  $('#input').disabled=state.recording||(state.busy&&!inFlight&&state.state!=='speaking');$('#send').disabled=disabled||!$('#input').value.trim();$('#mic').disabled=state.busy||!!inFlight;$('#voice-record').disabled=state.busy||!!inFlight;
  $('#voice-record').lastElementChild.textContent=state.recording?'Stop recording':'Start listening';
  $('#voice-state').textContent={idle:'Ready to listen',listening:'Listening to you',thinking:'A moment to think',speaking:'Flux is speaking',error:'Let’s reconnect'}[state.state]||'Ready';
  $('#mic').title=state.recording?'Stop recording':'Record voice';
}
function render(){
  const titles={chat:'Your space',memory:'Memory',voice:'Voice',settings:'Settings'};
  $('#page-title').textContent=titles[state.page];
  const current=state.sessions.find(s=>s.id===state.session);
  $('#header-detail').textContent=state.page==='chat'&&current?current.title:'A little clarity, whenever you need it.';
  for(const page of ['chat','memory','voice','settings'])$('#'+page+'-page').hidden=page!==state.page;
  $('#composer-area').hidden=!['chat','voice'].includes(state.page);
  document.querySelectorAll('[data-page]').forEach(e=>e.classList.toggle('active',e.dataset.page===state.page));
  $('#chat-count').textContent=state.sessions.length;$('#memory-count').textContent=state.memories.length;
  $('#model-label').textContent=state.model;$('#settings-model').textContent=state.model+' · Ollama';
  $('#auto-memory').checked=state.autoMemory;$('#reduce-motion').checked=state.reducedMotion;
  document.body.classList.toggle('reduced-motion',state.reducedMotion);
  $('#mode').replaceChildren(icon(state.mode==='voice'?'wave':'chat'),node('span','',state.mode==='voice'?'Voice mode':'Text mode'));
  renderSessions();renderMemories();renderMessages();renderStatus();
}
function openDialog(title,description,submit,callback,danger=false){
  const content=$('#modal-content');content.replaceChildren(node('h2','',title),node('p','',description));
  $('#modal-error').textContent='';$('#modal-submit').textContent=submit;$('#modal-submit').className=danger?'danger':'primary';modalAction=callback;cancelAction=null;
  $('#modal').showModal();return content;
}
function memoryDialog(memory=null){
  const content=openDialog(memory?'Edit memory':'Add a memory','A useful detail for future conversations. Up to 300 characters.','Save memory',()=>{
    const text=$('#memory-text').value.trim();if(!text){$('#modal-error').textContent='Write something to remember.';return false;}
    send('saveMemory',{id:memory?.id??null,text,category:$('#memory-category').value});return true;
  });
  const textLabel=node('label','','Memory');const input=node('textarea');input.id='memory-text';input.maxLength=300;input.value=memory?.content||'';input.required=true;textLabel.append(input);
  const categoryLabel=node('label','','Category');const select=node('select');select.id='memory-category';
  for(const category of ['Preferences','Personal','Projects','Goals','Work','Other']){const option=node('option','',category);option.value=category;select.append(option);}select.value=memory?.category||'Other';categoryLabel.append(select);content.append(textLabel,categoryLabel);input.focus();
}
function confirmDelete(data){
  const conversation=data.kind==='conversation',all=data.kind==='allMemories';
  openDialog(conversation?'Delete conversation?':all?'Clear all memories?':'Delete memory?',conversation?'This will permanently delete this conversation and its messages. Long-term memories are kept.':all?'This will remove all long-term memories. Conversation history is kept.':'This memory will be removed from future retrieval. Mentions in conversation history remain.',conversation?'Delete conversation':all?'Clear memories':'Delete memory',()=>{send('confirmDelete',{token:data.token});return true;},true);
  cancelAction=()=>send('cancelDelete');$('#modal-cancel').focus();
}
function receive(raw){
  const data=JSON.parse(raw);
  if(data.type==='snapshot'){state=data;render();document.body.dataset.ready='true';}
  else if(data.type==='status'&&state){Object.assign(state,data);renderStatus();}
  else if(data.type==='pending'){if(!pending)pending={text:data.text,phase:'sending'};}
  else if(data.type==='clearInput'){$('#input').value='';pending=null;inFlight=null;}
  else if(data.type==='turnCompleted'){pending=null;inFlight=null;}
  else if(data.type==='requestFailed'||data.type==='sendRejected'){
    if(inFlight){
      if(!$('#input').value)$('#input').value=inFlight.draft;
      if(pending)pending.phase='failed';
      inFlight=null;renderMessages();renderStatus();
    }
  }
  else if(data.type==='transcript'){$('#input').value=data.text;requestAnimationFrame(()=>$('#input').focus());}
  else if(data.type==='confirmDelete'){confirmDelete(data);}
  else if(data.type==='level'){FluxOrb.setLevel(data.value);}
}
function sendMessage(text=null,retry=false){
  if(!backend||!state||inFlight||state.busy||state.recording)return;
  const input=$('#input');const draft=text===null?input.value:text;
  const question=draft.trim();
  if(!question||question.length>4000)return;
  const command=question.startsWith('/');
  // Lock synchronously: rapid Enter/click events cannot dispatch a second request.
  inFlight={draft,text:question};pending=command?null:{text:question,phase:'sending'};
  if(!retry||input.value.trim()===question)input.value='';
  followLatest=true;
  if(!command){state.state='thinking';state.status='Thinking locally…';}
  renderMessages();renderStatus();
  $('#send').classList.remove('send-feedback');
  requestAnimationFrame(()=>$('#send').classList.add('send-feedback'));
  input.focus();
  send('send',{text:question});
}
$('#new-chat').onclick=()=>send('new');
document.querySelectorAll('[data-page]').forEach(e=>e.onclick=()=>send('page',{page:e.dataset.page}));
document.querySelectorAll('[data-prompt]').forEach(e=>e.onclick=()=>{$('#input').value=e.dataset.prompt;$('#input').focus();renderStatus();});
$('#search').oninput=()=>{if(state)renderSessions();};
$('#send').onclick=()=>sendMessage();
$('#input').oninput=()=>{if(state)renderStatus();};
$('#input').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!event.repeat)sendMessage();}};
$('#mic').onclick=$('#voice-record').onclick=()=>send('record');
$('#mode').onclick=()=>send('mode',{mode:state.mode==='text'?'voice':'text'});
$('#add-memory').onclick=()=>memoryDialog();
$('#clear-memories').onclick=()=>send('requestDelete',{kind:'allMemories'});
$('#auto-memory').onchange=e=>send('setting',{key:'auto_memory',value:e.target.checked});
$('#reduce-motion').onchange=e=>send('setting',{key:'reduced_motion',value:e.target.checked});
$('#modal-form').onsubmit=e=>{e.preventDefault();if(modalAction?.())$('#modal').close();};
$('#modal-cancel').onclick=()=>{cancelAction?.();$('#modal').close();};
$('#modal').oncancel=()=>cancelAction?.();
$('#rename-chat').onclick=()=>{const session=menuSession;$('#conversation-menu').hidden=true;const content=openDialog('Rename conversation','Give this conversation a title that’s easy to find.','Save title',()=>{const title=$('#rename-title').value.trim();if(!title){$('#modal-error').textContent='Enter a title.';return false;}send('rename',{id:session.id,title});return true;});const input=node('input');input.id='rename-title';input.maxLength=100;input.value=session.title;input.required=true;input.setAttribute('aria-label','Conversation title');content.append(input);input.focus();input.select();};
$('#delete-chat').onclick=()=>{const id=menuSession.id;$('#conversation-menu').hidden=true;send('requestDelete',{kind:'conversation',id});};
document.addEventListener('click',e=>{if(!e.target.closest('.context-menu')&&!e.target.closest('.session-menu-button'))$('#conversation-menu').hidden=true;});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('#conversation-menu').hidden=true;if(e.ctrlKey&&e.key.toLowerCase()==='n'&&!$('#modal').open){e.preventDefault();send('new');}});
if(typeof QWebChannel!=='undefined'&&typeof qt!=='undefined'){
  new QWebChannel(qt.webChannelTransport,channel=>{backend=channel.objects.flux;backend.event.connect(receive);send('ready');});
}else{
  $('#status').textContent='Open Flux through Python to connect this interface to your assistant.';
  document.querySelectorAll('button,input,textarea').forEach(e=>e.disabled=true);
}
