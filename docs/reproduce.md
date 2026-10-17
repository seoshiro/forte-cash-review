# Воспроизведение на Windows

> Историческая процедура исходного окружения. Для текущего запуска используйте [.venv-patched и README](../README.md#быстрый-запуск) и [локальный runbook](local-demo-runbook.md). Команды обучения/evaluate ниже не являются текущим разрешением повторять закрытые эксперименты или открывать TUNE/HOLDOUT.

Рабочая папка изолирована от исходников данных. Выполнять PowerShell из корня проекта, использовать именно .venv/Scripts/python.exe. Исходный XLSX и видео не изменять. Все JSON с наблюдениями, JPEG, локальные модели classifier и annotations сохраняются только в .private. Не открывать эти результаты через cloud browser/vision/capture.

## Окружение и артефакты

requirements.txt содержит прямые зависимости; requirements-lock.txt — фактическое окружение. После установки CUDA обновить lock и повторить dependency audit: предыдущий отчёт относится к CPU torch и не переносится автоматически на другую версию. Не включать экспериментальный Accelerate без необходимости; загрузка использует проверенные unsharded safetensors и не исполняет remote model code.

Состояние безопасно читать командой:

```powershell
.\.venv\Scripts\python.exe scripts/safe_status.py
```

Не запускать второй downloader. Сначала проверить status и процессы. Если artifact pipeline завершился, scripts/resume_downloads.py продолжает существующий contiguous partial и проверяет официальный SHA256 до установки/перемещения. scripts/restart_downloads.py допустим только на этапе download_preparation/blocked_download: он останавливает исключительно процессы скриптов загрузки этого проекта, сохраняет partial и прежние логи. Не вызывать его на inference/evaluation.

weights/provenance: модели не входят в Git. Qwen — models/provenance.json после завершения; DINO — models/dinov2-small/provenance.json. Теоретический размер tensor bytes не называть measured VRAM. Замер выделенной/зарезервированной памяти — в .private/benchmark/safe-summary.json после настоящего запуска.

## Split и протокол

.private/dataset/manifest.json сохраняет оригинальные ID, отдельный нормализованный ключ, PTS/rotation/decode сведения и hash. Split/frozen copies не генерировать заново для выбора удачного разбиения. Все кадры и аугментации исходного видео остаются в его split. Автоматическая проверка exact/near duplicates не заменяет ручную проверку семейств съёмки.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/evaluate.py --split tune --strategy uniform
.\.venv\Scripts\python.exe scripts/evaluate.py --split tune --strategy coarse_refine
```

Не запускать несколько GPU процессов одновременно. Benchmark прогревает модель на искусственных изображениях, затем измеряет TRAIN sequences. Evaluate сохраняет config, rules и split до анализа. Его latency отражает batch engine; загрузка модели указана отдельно. Для пяти минут жюри нужен отдельный upload→done API замер с cold worker/декодированием/evidence/очередью. Failed не превращается в отрицательный вердикт и показывается отдельно от quality metrics.

Holdout остаётся закрытым до выбора кандидата и проверки групп. Не устанавливать scene_groups_human_reviewed вручную без выполненной проверки. Повторный tuning считать exploratory; итоговый holdout нельзя повторно использовать для выбора улучшения без явного раскрытия.

## Проверки и приватность

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.private/test-run --junitxml=.private/test-report.xml
.\.venv\Scripts\python.exe scripts/claims.py
.\.venv\Scripts\python.exe scripts/audit_repo.py
```

UI QA разрешён только на synthetic_test server с whitelisted generated MOV. Обычный model mode и локальный annotation viewer запрещены для cloud screenshots. Изменения annotations не заменяют автоматический исходный result.

Python worker запрещает socket connect; FFmpeg отдельно ограничен MOV demuxer, локальным file handle и выключенными external tracks. Это не утверждение о физическом отключении сети: реальная автономность должна проверяться отдельно после подготовки весов. Не изменять защиту ОС ради теста.

Только loopback test value допустим в безопасных тестах. Публичный relay и постоянный API-ключ ждут отдельного прямого согласия; не использовать тестовое значение для жюри. Отсутствие публичного URL и неизвестный канал сдачи остаются блокерами сдачи.
