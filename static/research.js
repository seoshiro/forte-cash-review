'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const API = '/api/experimental/xclip';
  let key = '', busy = false, objectUrl = null, candidate = null, duration = 0, timer = null;
  let contextEnd = null;
  const stamp = seconds => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toFixed(2).padStart(5, '0')}`;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  function clear() {
    $('video').pause(); $('video').removeAttribute('src'); $('video').load();
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null; candidate = null; contextEnd = null;
    $('frames').replaceChildren(); $('timeline').replaceChildren();
    $('workspace').hidden = true; $('error').hidden = true; $('video-fallback').hidden = true;
    $('context-controls').hidden = true;
  }
  function failure(message) { clear(); $('error').textContent = message; $('error').hidden = false; }
  async function request(path, options, remaining) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), Math.max(1, remaining));
    try {
      const response = await fetch(path, {...options, headers: {'X-API-Key': key}, signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error'});
      if (!response.ok) {
        const messages = {401: 'Нужен верный ключ доступа.', 404: 'Задание недоступно для этого ключа.', 413: 'Файл превышает допустимый размер.', 429: 'Сервер занят. Повторите загрузку позже.', 503: 'Исследовательский сервер сейчас недоступен.'};
        throw new Error(messages[response.status] || 'Сервер не принял запрос. Результат не сформирован.');
      }
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  function validate(result, job) {
    const finite = n => typeof n === 'number' && Number.isFinite(n);
    const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k));
    const keys = ['job_id', 'status', 'mode', 'binary_decision', 'decision_margin', 'threshold', 'event_type_status', 'rule_application_status', 'candidate_timecode_sec', 'candidate_frames', 'duration_sec', 'elapsed_engine_sec', 'release_eligible', 'limitation'];
    const limitation = 'Binary research candidate only; type, physical explanation and legal rule are unverified. No complete multi-event detection claim.';
    if (!exact(result, keys) || !finite(result.elapsed_engine_sec) || result.elapsed_engine_sec < 0 || result.limitation !== limitation) throw new Error('Ответ не соответствует полной схеме прототипа.');
    if (result.job_id !== job || result.status !== 'done' || result.mode !== 'xclip_experimental' || result.event_type_status !== 'unverified' || result.rule_application_status !== 'not_assessed' || result.release_eligible !== false || result.threshold !== 0 || !finite(result.duration_sec) || result.duration_sec <= 0 || !finite(result.decision_margin)) throw new Error('Ответ не соответствует исследовательскому контракту.');
    const positive = result.binary_decision === 'violation';
    if (!['violation', 'no_violation'].includes(result.binary_decision) || positive !== (result.decision_margin >= 0) || !Array.isArray(result.candidate_frames)) throw new Error('Некорректный результат модели.');
    if (positive) {
      if (!finite(result.candidate_timecode_sec) || result.candidate_timecode_sec < 0 || result.candidate_timecode_sec > result.duration_sec || result.candidate_frames.length < 1 || result.candidate_frames.length > 3) throw new Error('Кандидат не подкреплён кадрами.');
      if (!result.candidate_frames.every(f => exact(f, ['timestamp_sec', 'image_base64']) && finite(f.timestamp_sec) && f.timestamp_sec >= 0 && f.timestamp_sec <= result.duration_sec && typeof f.image_base64 === 'string' && f.image_base64.length <= 8000000 && /^\/9j\/[A-Za-z0-9+/]*={0,2}$/.test(f.image_base64))) throw new Error('Некорректные кадры кандидата.');
      if (!result.candidate_frames.some(f => Math.abs(f.timestamp_sec - result.candidate_timecode_sec) < 1e-6)) throw new Error('Время кандидата не совпадает с кадром.');
    } else if (result.candidate_timecode_sec !== null || result.candidate_frames.length !== 0) throw new Error('Несогласованные данные отрицательного результата.');
    return positive;
  }
  function seek(sec) { contextEnd = null; $('video').pause(); $('video').currentTime = Math.max(0, Math.min(duration, sec)); }
  async function render(result, job, file) {
    const positive = validate(result, job);
    const images = await Promise.all(result.candidate_frames.map(async frame => {
      const image = new Image(); image.alt = `Кадр ${stamp(frame.timestamp_sec)}`;
      image.src = `data:image/jpeg;base64,${frame.image_base64}`;
      await image.decode(); return {image, frame};
    }));
    duration = result.duration_sec; candidate = result.candidate_timecode_sec;
    objectUrl = URL.createObjectURL(file); $('video').src = objectUrl;
    $('verdict').textContent = positive ? 'Есть кандидат для ручной проверки' : 'Кандидат не найден';
    $('result-note').textContent = positive ? 'Это предложение посмотреть эпизод. Нарушение, его тип и правило не установлены.' : 'Этот результат не подтверждает отсутствие нарушения: качество бинарной модели недостаточно.';
    $('candidate-title').textContent = positive ? `Момент ${stamp(candidate)}` : 'Положительный кандидат не предложен';
    $('established').textContent = positive ? 'Оценка локальной бинарной модели пересекла фиксированный порог. Ниже доступны исходные кадры и контекст.' : 'Оценка модели не пересекла фиксированный порог. Проверка человеком по-прежнему необходима.';
    for (const {image, frame} of images) {
      const button = document.createElement('button'); button.className = 'frame'; button.type = 'button';
      const label = document.createElement('span'); label.textContent = stamp(frame.timestamp_sec);
      button.append(image, label); button.addEventListener('click', () => seek(frame.timestamp_sec)); $('frames').append(button);
    }
    if (positive) {
      const marker = document.createElement('button'); marker.type = 'button'; marker.textContent = stamp(candidate); marker.title = 'Перейти к кандидату';
      marker.style.left = `${Math.max(4, Math.min(96, 100 * candidate / duration))}%`;
      marker.addEventListener('click', () => seek(candidate)); $('timeline').append(marker); $('context-controls').hidden = false;
    }
    $('empty').hidden = true; $('workspace').hidden = false;
  }
  $('access').addEventListener('click', () => { if (!busy) $('key-dialog').showModal(); });
  $('save-key').addEventListener('click', () => { key = $('key').value.trim(); $('key').value = ''; clear(); $('empty').hidden = false; });
  $('file').addEventListener('change', () => { if (!busy) { clear(); $('empty').hidden = false; $('filename').textContent = $('file').files[0]?.name || 'Выберите видео'; } });
  $('video').addEventListener('error', () => { if (objectUrl) $('video-fallback').hidden = false; });
  $('video').addEventListener('timeupdate', () => { if (contextEnd !== null && $('video').currentTime >= contextEnd) { $('video').pause(); contextEnd = null; } });
  $('before').addEventListener('click', () => { if (candidate !== null) seek(candidate - 3); });
  $('after').addEventListener('click', () => { if (candidate !== null) seek(candidate + 3); });
  $('context').addEventListener('click', async () => { if (candidate !== null) { seek(candidate - 3); contextEnd = Math.min(duration, candidate + 3); try { await $('video').play(); } catch { $('video-fallback').hidden = false; } } });
  $('upload').addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    if (!key) { $('key-dialog').showModal(); return; }
    const file = $('file').files[0]; if (!file) return;
    clear();
    if (!/\.mov$/i.test(file.name) || file.size > 128 * 1024 * 1024) { failure('Выберите MOV размером до 128 МБ.'); return; }
    busy = true; for (const id of ['submit', 'file', 'access']) $(id).disabled = true;
    $('empty').hidden = true; $('statusbox').hidden = false;
    const start = performance.now(), deadline = start + 300000;
    timer = setInterval(() => { $('elapsed').textContent = stamp((performance.now() - start) / 1000); }, 250);
    try {
      const form = new FormData(); form.append('file', file);
      const accepted = await request(`${API}/analyze`, {method: 'POST', body: form}, deadline - performance.now());
      if (typeof accepted.job_id !== 'string' || !/^[0-9a-f]{32}$/.test(accepted.job_id)) throw new Error('Сервер не вернул корректный номер задания.');
      while (performance.now() < deadline) {
        const result = await request(`${API}/jobs/${accepted.job_id}`, {method: 'GET'}, deadline - performance.now());
        if (result.job_id !== accepted.job_id) throw new Error('Получен ответ другого задания.');
        if (result.status === 'done') { await render(result, accepted.job_id, file); return; }
        if (result.status === 'failed') throw new Error('Техническая ошибка анализа. Вердикт не сформирован.');
        if (result.status !== 'processing') throw new Error('Неизвестное состояние задания.');
        await pause(1000);
      }
      throw new Error('Пять минут истекли. Результат анализа не получен.');
    } catch (error) { failure(error.name === 'AbortError' ? 'Время ожидания истекло. Вердикт не сформирован.' : error.message || 'Техническая ошибка.'); }
    finally { clearInterval(timer); timer = null; $('statusbox').hidden = true; busy = false; for (const id of ['submit', 'file', 'access']) $(id).disabled = false; }
  });
  window.addEventListener('pagehide', () => { key = ''; clearInterval(timer); if (objectUrl) URL.revokeObjectURL(objectUrl); });
})();
