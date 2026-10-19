import {mkdir, readFile, writeFile, copyFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('..', import.meta.url)));
await mkdir('dist/assets', {recursive:true});
for (const name of ['style.css','motion.css','plasma.js','orb.js','app.js']) {
  let text = await readFile(`flux/frontend/${name}`, 'utf8');
  text = text.replaceAll('../assets/', 'assets/');
  if (name === 'app.js') text = text.replace("+' · Ollama'", "+' · Server'").replaceAll('Thinking locally…','Thinking…').replace(
    "$('#status').textContent='Open Flux through Python to connect this interface to your assistant.';\n  document.querySelectorAll('button,input,textarea').forEach(e=>e.disabled=true);",
    'window.connectFluxWeb(receive, value => { backend = value; send("ready"); });');
  if (name === 'app.js' && !text.includes('window.connectFluxWeb(receive')) throw new Error('Browser connection entry point was not generated.');
  await writeFile(`dist/${name}`, text);
}
let html = await readFile('flux/frontend/index.html','utf8');
html = html.replaceAll('../assets/', 'assets/').replace('qrc:///qtwebchannel/qwebchannel.js','web.js')
  .replace("script-src 'self' qrc:","script-src 'self'").replace("connect-src 'none'", "connect-src 'self' https: http://localhost:* http://127.0.0.1:*")
  .replace('Private. Personal. On your PC.','Your personal web assistant.').replace('LOCAL FIRST','WEB EDITION')
  .replace('Your voice stays on your PC.','Speech recognition may use your browser’s cloud service.')
  .replace('Everything stays on this PC.','Your history is saved on your Flux server.')
  .replace('Whisper · local','Browser speech recognition').replace('Windows voices · local','Browser voices')
  .replace('SQLite · on this PC','SQLite · on your Flux server')
  .replace('History is stored in data/flux.db without encryption. The upgrade preserves a one-time backup of older data.', 'History is stored on your API server. All holders of your access key share this workspace.')
  .replace('or the upgrade backup.','or server backups.');
await writeFile('dist/index.html',html);
await copyFile('web/web.js','dist/web.js');
await copyFile('flux/assets/flux-orb.png','dist/assets/flux-orb.png');
console.log('Netlify frontend built in dist/');
