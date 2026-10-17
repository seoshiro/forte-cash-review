# Контур · Datathon NU 2026 / ForteBank

Локальный сервис проверки визуальных признаков кассовых нарушений. Наблюдение → условие нормы → последовательность доказательств. Только визуальный анализ локальной моделью. Автоматическая подсказка не заменяет решение человека.

## Состояние

Проект в разработке. Работоспособность HTTP-контракта проверяется на искусственных MOV отдельно от качества модели. CPU baseline не перенёс качество на tuning. Qwen/CUDA ещё готовятся; готовность к отбору не подтверждена. Актуальные измерения: docs/measured-checkpoint.md и docs/claim-ledger.csv. Подробные данные остаются в .private.

## Запуск Windows

Python 3.12.11, отдельная .venv, зависимости requirements.txt. Torch 2.8.0 и torchvision 0.23.0 устанавливаются из https://download.pytorch.org/whl/cu128. Рабочие версии дополнительно фиксируются в requirements-lock.txt после установки. PyAV включает свои FFmpeg libraries, внешний ffmpeg CLI не требуется.

```powershell
.\.venv\Scripts\python.exe scripts/resume_downloads.py qwen
$env:CASH_API_KEY='<локально установленный ключ>'
.\.venv\Scripts\python.exe scripts/serve.py
```

Первое скачивание весов требует сети. Запросы обрабатываются с HF_HUB_OFFLINE, TRANSFORMERS_OFFLINE, local_files_only и запретом socket connect внутри worker. Не отключайте защиту ОС. Постоянный ключ/новые persistent grants/изменение сетевых настроек требуют отдельного разрешения пользователя.

UI: http://127.0.0.1:8765/. Ключ вводится пользователем и хранится только в памяти вкладки. Он не в JS сборке. Public HTTPS настраивается отдельно, состояние не предполагается из локального запуска.

```powershell
curl.exe -X POST http://127.0.0.1:8765/api/v1/analyze -H "X-API-Key: $env:CASH_API_KEY" -F 'file=@new.mov'
curl.exe http://127.0.0.1:8765/api/v1/jobs/JOB_ID -H "X-API-Key: $env:CASH_API_KEY"
```

Схема в cashreview/schemas.py; при техническом сбое status=failed. Одновременная обработка ограничена одним worker: лишняя загрузка получает 429 до создания задания. Жёсткий общий budget принятого задания до 295 с плюс передача HTTP. Отсчёт начинается при приёме файла; длительная сеть учитывается в оставшемся времени обработки. В UI deadline 300 с включает загрузку, polling. Модель не скачивается по запросу; холодная загрузка пока включена в время задания. Очередь не маскирует задержку.

## Данные и оценка

```powershell
.\.venv\Scripts\python.exe scripts/manifest.py --videos 'C:\Users\gokusen\Downloads\open\videos' --labels 'C:\Users\gokusen\Downloads\open\open_labels.xlsx'
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/evaluate.py --split tune --strategy uniform
.\.venv\Scripts\python.exe scripts/evaluate.py --split tune --strategy coarse_refine
```

Скрипты выводят только агрегаты и технические сведения. Персональные outputs, предсказания, evidence и аннотации не печатать и не передавать внешним инструментам. Не открывать реальные банковские кадры через cloud vision/browser capture. Для UI QA только scripts/synthetic.py и -SyntheticTest. SyntheticTest проверяет только whitelisted hashes искусственных файлов; это не детектор.

Holdout закрыт по умолчанию. Нужны проверка семейств сцен и заморозка конфигурации; evaluate.py не позволяет молча открыть его повторно. Кадры исходного ролика не разделяются между split. Поиск ответов по имени запрещён; сервис сохраняет загрузку как случайный jobs/<opaque>/input.mov и не читает labels.

## Приватность

.private, models, runtime/cache, все видео/кадры/таблицы/локальные outputs исключены из Git. Нет внешних CDN, аналитики, cloud inference, audio decoding, face recognition. Изоляция результатов: случайный job_id и hash владельца ключа; чужой ключ получает 404. Данные удаляются через час. После конкурса исходные данные и рабочие копии должны быть очищены пользователем по регламенту; текущий код исходники не удаляет и не изменяет.

Перед code-only публикацией запустить scripts/audit_repo.py и просмотреть staged files. Пока repo только локальный; публикацию и фактическую сдачу не считать выполненными.

## Лицензии

Собственный код — Apache-2.0. Qwen3-VL-2B-Instruct: Apache-2.0 по официальной model card https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct; код модели https://github.com/QwenLM/Qwen3-VL, Transformers Apache-2.0. Точная ревизия загрузки — локально models/provenance.json. Код и веса проверяются отдельно. Прочие зависимости и включённые FFmpeg libraries перечисляются в docs/licenses.md. Соблюдайте upstream notices при распространении.
