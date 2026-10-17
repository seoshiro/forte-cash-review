'use strict';
// Local UI only. No push subscriptions, external messages or training hooks.
let reviewEpoch=0,reviewTimer=null,reviewState=null;
const decisionLabels={confirmed:'Подтверждено проверяющим',rejected:'Отклонено проверяющим',insufficient_data:'Недостаточно данных'};
const originalRender=render,originalSelect=select;
function clearReview(){reviewEpoch++;clearTimeout(reviewTimer);reviewState=null;$('review-notification').hidden=true;}
const originalChoose=choose;
choose=function(file){if(file){clearReview();current=null;details=null;$('workspace').hidden=true;$('empty').hidden=false;}originalChoose(file);};
$('upload').addEventListener('submit',()=>{if(apiKey&&picked)clearReview();},true);
render=function(){
  originalRender();clearReview();
  current.violations.forEach((event,index)=>{
    const card=$('event-'+index),panel=node('section',undefined,'review-panel');
    panel.append(node('h4','ПРОВЕРКА КОНТЕКСТА'),node('p','Получаем результат проверки…','context-result'),node('p','','context-limitation note'));
    panel.append(node('h4','РЕШЕНИЕ ПРОВЕРЯЮЩЕГО'),node('p','Ещё не рассмотрено','review-decision'));
    const note=node('textarea');note.rows=2;note.maxLength=800;note.placeholder='Комментарий (необязательно)';note.setAttribute('aria-label','Комментарий проверяющего');panel.append(note);
    const actions=node('div',undefined,'review-actions');
    [['confirmed','Подтвердить'],['rejected','Отклонить'],['insufficient_data','Недостаточно данных']].forEach(([value,label])=>{
      const button=node('button',label,'quiet');button.type='button';button.dataset.decision=value;button.disabled=true;
      button.onclick=()=>saveReview(index,value,note.value);actions.append(button);
    });
    panel.append(actions,node('p','','review-feedback'),node('p','Решение хранится отдельно. Исходный результат модели сохраняется; автоматического обучения и санкций нет.','review-caption'));
    card.append(panel);
  });
  if(current.violations.length)loadReviews(reviewEpoch,current.job_id);
};
select=function(index){originalSelect(index);if($('event-'+index)?.querySelector('.review-panel')&&current?.status==='done')loadReviews(reviewEpoch,current.job_id);};
function applyReviewState(state){
  reviewState=state;
  current.violations.forEach((_,index)=>{
    const panel=$('event-'+index)?.querySelector('.review-panel');if(!panel)return;
    const context=state.contexts?.[index]||{status:'pending'},saved=state.reviews?.[String(index)];
    const title=context.status==='reviewed'?'Контекст повторно проверен на доступных кадрах.':context.status==='limited'?'Контекст ограничен.':'Проверка контекста ещё не завершена.';
    panel.querySelector('.context-result').textContent=title+(context.result?' '+context.result:'');
    panel.querySelector('.context-limitation').textContent=context.limitation||'';
    panel.querySelector('.review-decision').textContent=saved?decisionLabels[saved.decision]:'Ещё не рассмотрено';
    const note=panel.querySelector('textarea');if(document.activeElement!==note)note.value=saved?.note||'';
    panel.querySelectorAll('[data-decision]').forEach(button=>{button.disabled=!state.ready;button.setAttribute('aria-pressed',String(saved?.decision===button.dataset.decision));});
  });
  const notice=$('review-notification');notice.hidden=!(state.ready&&state.notification&&current.status==='done');
  if(!notice.hidden){const count=state.notification.unreviewed_count;notice.textContent=count?`Анализ завершён. ${episodes(count)} ожидают ручной проверки.`:'Решения проверяющего сохранены. Автоматический результат модели не изменён.';}
}
async function loadReviews(epoch,job){
  try{
    const state=await request('/api/ui/jobs/'+job+'/reviews');
    if(epoch!==reviewEpoch||current?.job_id!==job)return;
    applyReviewState(state);clearTimeout(reviewTimer);
    if(!state.ready)reviewTimer=setTimeout(()=>loadReviews(epoch,job),1200);
  }catch(error){if(epoch!==reviewEpoch)return;$('review-notification').hidden=true;document.querySelectorAll('.review-feedback').forEach(item=>item.textContent='Решения пока недоступны. '+error.message);}
}
async function saveReview(index,decision,note){
  const epoch=reviewEpoch,job=current.job_id,panel=$('event-'+index).querySelector('.review-panel');
  panel.querySelectorAll('button').forEach(button=>button.disabled=true);
  panel.querySelector('.review-feedback').textContent='Сохраняем решение…';
  try{
    const state=await request('/api/ui/jobs/'+job+'/reviews/'+index,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,note})});
    if(epoch!==reviewEpoch||current?.job_id!==job)return;
    applyReviewState(state);panel.querySelector('.review-feedback').textContent='Решение сохранено отдельно от прогноза модели.';
  }catch(error){if(epoch!==reviewEpoch)return;panel.querySelector('.review-feedback').textContent=error.message;panel.querySelectorAll('button').forEach(button=>button.disabled=!reviewState?.ready);}
}
