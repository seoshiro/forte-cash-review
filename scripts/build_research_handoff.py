"""Build a private shareable synthetic/aggregate-only handoff, never include keys/data."""
from pathlib import Path
import hashlib,html,json,shutil,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
IMAGES={'empty-desktop.png':'70f6e1c68742ca047aa197d797b0268c43bd9cb6b6242d88704ed58e6a181a74',
        'candidate-desktop.png':'a8ca2a719ddd5b4da4562cae4db8b12a9a0c7eaf9266f62d3e7cbcac8dcb9cb1',
        'candidate-mobile.png':'4a0b3394fcc4c173dd408476e516e2e62efc7e710fecc1502628d7047618a2a9'}


def main():
    private=ROOT/'.private';out=private/'research-handoff';out.mkdir(exist_ok=True)
    access=json.loads((private/'research-access-live/safe-summary.json').read_text());network=json.loads((private/'research-access-live/synthetic-safe-summary.json').read_text())
    result=json.loads((private/'xclip-last-layer-recovery/safe-summary.json').read_text());calculation=json.loads((private/'xclip-last-layer-recovery/calculation-safe-summary.json').read_text())
    endpoint=json.loads((private/'research-access-live/endpoint.json').read_text())
    assert access['status']=='READY' and access['synthetic_full_cycle_verified'] and network['status']=='PASS' and endpoint['active_expected'] and time.time()<endpoint['expires_unix']
    assert calculation['status']=='PASS' and result['status'] in ['completed','failed']
    image_dir=out/'images';image_dir.mkdir(exist_ok=True)
    for name,digest in IMAGES.items():
        source=private/'presentation-ui'/name
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        shutil.copyfile(source,image_dir/name)
    rows=[]
    if result['status']=='completed':
        for name in ['baseline','regularized_frozen_head','last_layer_adapter']:
            value=result['results'][name];cm=value['confusion_matrix_tn_fp_fn_tp']
            rows.append((name,cm[0][0],cm[0][1],cm[1][0],cm[1][1],value['precision'],value['recall'],value['f1'],value['all_positive_candidate_point_mae_sec']))
        quality=('Адаптер отклонён по зафиксированному joint gate; baseline сохранён. ' if not result['joint_gate_passed'] else 'Экспериментальные TRAIN gates пройдены; это не семантическая приёмка. ')+'Полный исследовательский TRAIN grouped OOF завершён. Gates: binary='+str(result['binary_gate_passed'])+', point='+str(result['point_gate_passed'])+', joint='+str(result['joint_gate_passed'])+'.'
    else:quality='Полного OOF нет: технический проход завершился с ошибкой. Сохранённых полных fit checkpoints: '+str(result.get('completed_fit_checkpoints',0))+'. Частичные метрики качества не публикуются.'
    table='| Model | TN | FP | FN | TP | Precision | Recall | F1 | All-positive point MAE, s |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
    for row in rows:table+='| '+' | '.join(str(v) if not isinstance(v,float) else f'{v:.6f}' for v in row)+' |\n'
    results='# Результаты и практические ограничения\n\n'+quality+'\n\n'+(table if rows else '')+'\nЭто повторно использованный exploratory TRAIN, не независимая оценка и не официальный балл. Автоматические группы не проверены экспертом; разметка содержит не исчерпывающий point, а не границы/типы событий. TUNE и HOLDOUT в этом этапе закрыты.\n\nПубличный сервис продолжает использовать сохранённый cosine baseline. Новый adapter не подменяет его автоматически. Исходная однократная TUNE-оценка baseline: TN1 FP3 FN4 TP1, F1=0.222222 на9 исходных видео; она не повторялась.\n\nПубличный upload-to-done проверен только на искусственном MOV. Wall: '+str(network['public_upload_to_done_wall_sec'])+'s; это техническая демонстрация, не качество распознавания банковских действий.\n\nТипы событий, физические объяснения, применимость правил, полнота нескольких событий и устойчивость к новой камере не подтверждены. Конкурсный API остаётся закрыт503; исследовательский API отделён.\n'
    (out/'RESULTS.md').write_text(results,encoding='utf-8')
    architecture='''# Архитектура и лицензии

Браузер с локальными assets → защищённый HTTPS relay → origin на Windows loopback8769 → изолированные фоновые jobs → локальный XCLIP encoder → бинарный research scorer → реальные JPEG/PTS кандидата только по авторизованному запросу. Работающий research scorer — сохранённый cosine baseline; его event type и rule application имеют статусы unverified/not_assessed.

Cloudflare передаёт HTTPS-трафик и не выполняет AI-анализ. Модели загружены локально; worker запрещает исходящие сетевые вызовы. Звук, распознавание/идентификация лиц и lookup ответов по именам не используются. Dataset, результаты, веса и ключи отсутствуют в code-only Git.

Адаптация изучалась отдельно: последние MIT fc2 LoRA rank2, temporal head, фиксированная регуляризация, оригинал и единообразное изменение яркости/контраста. Все параметры и gates фиксировались до запуска. Это не доказательство семантического распознавания.

Текущий XCLIP: microsoft/xclip-base-patch32, revision a2e27a78a2b5d802e894b8a1ef14f3a8ce490963. Веса — MIT; native Transformers — Apache-2.0; upstream VideoX — MIT. Собственный код — LICENSE в комплекте. Исходники и точные dependency locks находятся в приватном репозитории https://github.com/seoshiro/forte-cash-review . Бинарные зависимости/веса в архив не включены; их notices и условия применяются отдельно, см. licenses.md.
'''
    (out/'ARCHITECTURE.md').write_text(architecture,encoding='utf-8')
    rules='''# Нормативные источники и границы

Публичная отправная точка: Постановление Правления НБРК от29 ноября2019 №231, https://adilet.zan.kz/rus/docs/V1900019680 . Проверка официального происхождения/редакции и цитат сохранена в репозитории docs/legal-source-provenance.md. Этот источник не означает автоматическую применимость любого пункта к любому фрагменту.

У research модели нет принятого классификатора типов действий и применения правил. Она не создаёт ссылки, номера пунктов или внутренние правила ForteBank. Банковские проводки, сверка, права доступа людей и невидимые обстоятельства не устанавливаются по кадру. Решение для проверки человеком; юридическое/дисциплинарное заключение не выдаётся.
'''
    (out/'RULES_AND_LIMITS.md').write_text(rules,encoding='utf-8')
    (out/'PITCH_5MIN.md').write_text('''# Короткая демонстрация для пользователя

0:00–0:45 — честный статус: исследовательский локальный бинарный прототип; обязательная семантическая часть конкурса не подтверждена.
0:45–2:00 — открыть защищённый интерфейс, ввести ключ из локального окна, загрузить только искусственный MOV для публичной демонстрации. Показать статус, кандидатную временную точку и ограничения; не выдавать синтетическую сцену за банковское событие.
2:00–3:00 — показать таблицу RESULTS.md. Разделить полные OOF-агрегаты, технические HTTP-тесты и старую TUNE. Если полного OOF нет, сказать это прямо.
3:00–4:00 — показать локальность inference, owner isolation, отсутствие ключа в JS и безопасность временного доступа. Рассказать об атомарных complete-fit checkpoints и точном resume на синтетике.
4:00–5:00 — открытые проблемы: типы/правила, независимая камера, недостаток независимых измерений; не утверждать готовность к сдаче. Обсудить следующий этап локальной экспертной разметки и проверки.
''',encoding='utf-8')
    shutil.copyfile(ROOT/'LICENSE',out/'LICENSE');shutil.copyfile(ROOT/'docs/licenses.md',out/'licenses.md')
    table_html='<table><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in ['Model','TN','FP','FN','TP','Precision','Recall','F1','Point MAE'])+'</tr>'
    for row in rows:table_html+='<tr>'+''.join('<td>'+html.escape(f'{v:.4f}' if isinstance(v,float) else str(v))+'</td>' for v in row)+'</tr>'
    table_html+='</table>'
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>TerenOi — research handoff</title><style>body{margin:0;background:#101a27;color:#eef4fc;font:20px/1.55 Arial,sans-serif}section{min-height:92vh;padding:4vh 7vw;box-sizing:border-box;border-bottom:1px solid #38506b}h1{font-size:54px;line-height:1.1}h2{font-size:36px}.tag{color:#ffc66c;font-weight:bold}img{max-width:95%;max-height:68vh;object-fit:contain}table{border-collapse:collapse;font-size:18px}th,td{padding:12px;border:1px solid #456}a{color:#8ac7ff}.small{font-size:17px;color:#c5d2e3}@media print{section{page-break-after:always;height:100vh}body{background:white;color:black}}</style>'''
    page+='<section><p class="tag">Исследовательский прототип · не подтверждено соответствие конкурсу</p><h1>TerenOi</h1><p>Локальная проверка видео: бинарный кандидат, временная точка и рабочее место человека.</p><p><a href="'+html.escape(access['url'])+'">Открыть защищённый research UI</a></p><p class="small">Ключ — только в локальном окне на Windows. Типы событий и правила не подтверждены.</p></section>'
    for name,label in [('empty-desktop.png','Загрузка'),('candidate-desktop.png','Кандидат и контекст'),('candidate-mobile.png','Мобильный интерфейс')]:
        page+='<section><h2>'+label+'</h2><p class="tag">СИНТЕТИЧЕСКИЙ ПРИМЕР ИНТЕРФЕЙСА; качество детектора не демонстрируется</p><img src="images/'+name+'"></section>'
    page+='<section><h2>Измерения</h2><p>'+html.escape(quality)+'</p>'+table_html+'<p class="small">Exploratory TRAIN OOF; не официальный балл и не независимая валидация. Публичный upload-to-done проверен только на искусственном MOV. Старый baseline TUNE F1=0.222222.</p></section>'
    page+='<section><h2>Что остаётся проверить</h2><p>Типы действий и правила, ошибки на похожих корректных действиях, несколько событий, новый ракурс, независимое качество.</p><p>Сохранённый baseline продолжает работать в research UI. Конкурсный API закрыт503. Ключи, банк-видео, кадры, разметка и частные результаты не включены в материалы.</p></section></html>'
    (out/'presentation.html').write_text(page,encoding='utf-8')
    readme=out/'README.txt'
    readme.write_text(readme.read_text(encoding='utf-8').replace('Финальная техническая сводка и ограничения будут рядом после завершения фиксированного OOF.','Полный результат и ограничения: RESULTS.md. Подход последнего слоя отклонён; baseline сохранён.'),encoding='utf-8')
    names=['README.txt','RESULTS.md','ARCHITECTURE.md','RULES_AND_LIMITS.md','PITCH_5MIN.md','presentation.html','LICENSE','licenses.md']+['images/'+name for name in IMAGES]
    archive=private/'TerenOi-research-handoff.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as stream:
        for name in names:stream.write(out/name,arcname=name)
    report={'status':'PASS','scope':'Private user handoff: verified synthetic PNGs and aggregate/code-only explanatory materials, never secrets or bank artifacts',
            'archive_files':len(names),'synthetic_images':len(IMAGES),'archive_bytes':archive.stat().st_size,'secrets_or_bank_data_included':False,'release_eligible':False}
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()
