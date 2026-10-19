'use strict';
window.connectFluxWeb = (receive, connected) => {
  const emit = data => receive(JSON.stringify(data));
  let endpoint = '', accessKey = '', recognition = null, recording = false;
  const status = message => emit({type:'status',state:'error',status:message,busy:false,recording:false});
  const dialog = document.createElement('dialog');
  const form = document.createElement('form');
  const title = document.createElement('h2'); title.id='connect-title'; title.textContent = 'Connect to Flux'; dialog.setAttribute('aria-labelledby',title.id);
  const description = document.createElement('p'); description.textContent = 'Enter your Flux API server and private access key. The key stays in this tab’s memory. Everyone with this key shares the same workspace.';
  const urlLabel = document.createElement('label'); urlLabel.textContent = 'Server URL';
  const url = document.createElement('input'); url.type = 'url'; url.required = true; url.placeholder = 'https://your-flux-api.example.com'; urlLabel.append(url);
  const keyLabel = document.createElement('label'); keyLabel.textContent = 'Access key';
  const key = document.createElement('input'); key.type = 'password'; key.required = true; key.minLength = 32; key.autocomplete = 'off'; keyLabel.append(key);
  const error = document.createElement('p'); error.setAttribute('role','alert');
  const button = document.createElement('button'); button.type = 'submit'; button.className = 'primary'; button.textContent = 'Connect';
  const actions = document.createElement('div'); actions.className='modal-actions'; actions.append(button);
  form.append(title,description,urlLabel,keyLabel,error,actions); dialog.append(form); document.body.append(dialog);
  dialog.addEventListener('cancel', e => e.preventDefault());
  async function request(data) {
    const response = await fetch(endpoint + '/api/action', {method:'POST', headers:{'Content-Type':'application/json',Authorization:'Bearer '+accessKey},body:JSON.stringify(data)});
    if (!response.ok) throw new Error(response.status === 401 ? 'Incorrect access key.' : response.status === 409 ? 'Flux is busy in another tab. Try again shortly.' : 'Server request failed ('+response.status+').');
    return (await response.json()).events;
  }
  function voice() {
    if (recording) { recognition.stop(); return; }
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Speech) { status('Speech recognition is unavailable in this browser. You can still type your message.'); return; }
    recognition = new Speech(); recognition.lang = 'en-US'; recognition.interimResults = false;
    recognition.onstart = () => {recording=true; emit({type:'status',state:'listening',status:'Listening. Stop when finished.',busy:false,recording:true});};
    recognition.onresult = e => emit({type:'transcript',text:e.results[0][0].transcript.slice(0,4000)});
    recognition.onerror = () => status('Speech recognition failed. Check microphone permission or type your message.');
    recognition.onend = () => {recording=false; emit({type:'status',state:'idle',status:'Review your message, then Send.',busy:false,recording:false});};
    recognition.start();
  }
  const backend = {async dispatch(raw) {
    const data = JSON.parse(raw);
    try {
      if(data.action==='copy') {await navigator.clipboard.writeText(data.text);return;}
      if(data.action==='record') {voice();return;}
      for(const event of await request(data)) {
        if(event.type==='speak') { if('speechSynthesis' in window) {speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(event.text));} }
        else emit(event);
      }
    } catch(e) { status(e.message || 'Cannot connect to Flux. Check your server and connection.'); if(data.action==='send') emit({type:'sendRejected'}); }
  }};
  form.onsubmit = async e => {
    e.preventDefault(); button.disabled=true; error.textContent='Connecting…';
    try {
      const parsed = new URL(url.value);
      if(parsed.protocol!=='https:' && !(parsed.protocol==='http:' && ['localhost','127.0.0.1'].includes(parsed.hostname))) throw new Error('Use an HTTPS server URL. HTTP is allowed only for local development.');
      endpoint=parsed.origin; accessKey=key.value;
      const events = await request({action:'ready'});
      dialog.close(); key.value=''; connected(backend); for(const event of events) emit(event);
    } catch(e) {error.textContent=e.message || 'Cannot connect. Check the server URL and allowed website origin.';accessKey='';}
    finally {button.disabled=false;}
  };
  dialog.showModal();
};
