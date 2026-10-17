'use strict';
history.replaceState(null,'','/');
const $=id=>document.getElementById(id),fields=['label_matches','rule_or_type','visibility','comment','reviewed_time_sec'];
let items=[],current=0,drafts={};
async function request(url,options){const response=await fetch(url,options);if(!response.ok)throw new Error('Локальный запрос не выполнен ('+response.status+').');return response.json()}
function values(){const a={};for(const id of fields)a[id]=$(id).value;a.reviewed_time_sec=a.reviewed_time_sec===''?null:Number(a.reviewed_time_sec);return a}
function format(t){return t===null?'не указано':Math.floor(t/60)+':'+(t%60).toFixed(2).padStart(5,'0')}
function progress(){const n=items.filter(x=>x.annotation).length;$('progress').textContent=`Сохранено ${n} из ${items.length}. `+(n===items.length?'Готово. В чат достаточно написать «готово».':'Сохраняйте каждый просмотренный ролик.');for(const b of $('cases').children){const i=Number(b.dataset.index);b.classList.toggle('saved',Boolean(items[i].annotation));b.setAttribute('aria-current',String(i===current))}}
function show(index){if(items[current])drafts[current]=values();current=index;const item=items[index];$('title').textContent=`Ролик ${index+1} из ${items.length}`;$('meta').textContent=`Официальная метка: ${item.target?'нарушение':'без нарушения'}. Отметка: ${format(item.label_sec)}. Длительность: ${item.duration_sec.toFixed(2)} с.`;
 $('video').pause();$('video').src='/media/'+item.case_id;$('video-error').hidden=true;$('seek').disabled=item.label_sec===null;$('reviewed_time_sec').max=String(item.duration_sec);const a=drafts[index]||item.annotation||{};for(const id of fields)$(id).value=a[id]??'';$('feedback').textContent=item.annotation?'Ранее сохранённая ручная пометка загружена.':'';$('save').textContent=index===items.length-1?'Сохранить последний ролик':'Сохранить и дальше';progress()}
$('seek').onclick=()=>{if(items[current].label_sec!==null)$('video').currentTime=items[current].label_sec};
$('use-time').onclick=()=>{$('reviewed_time_sec').value=$('video').currentTime.toFixed(2)};
$('video').ontimeupdate=()=>{$('clock').textContent=format($('video').currentTime)};
$('video').onerror=()=>{$('video-error').hidden=false};
$('form').oninput=()=>{$('feedback').textContent='Изменения ещё не сохранены.'};
$('form').onsubmit=async event=>{event.preventDefault();$('save').disabled=true;try{const answers=values();await request('/api/annotations/'+items[current].case_id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(answers)});items[current].annotation=answers;drafts[current]=answers;progress();$('feedback').textContent='Сохранено только локально.';if(current<items.length-1)show(current+1)}catch(error){$('feedback').textContent=error.message}finally{$('save').disabled=false}};
request('/api/items').then(data=>{items=data.items;items.forEach((item,index)=>{const b=document.createElement('button');b.type='button';b.dataset.index=index;b.textContent=String(index+1);b.onclick=()=>show(index);$('cases').append(b)});current=-1;show(0)}).catch(error=>{$('fatal').hidden=false;$('fatal').textContent=error.message});
