# Контур · Datathon NU 2026 / ForteBank

[Текущий checkpoint](docs/current-checkpoint.md): отдельный исследовательский API прошёл два запроса с настоящим XCLIP на искусственном MOV; это проверка интеграции, а не банковского качества. Закреплены веса, конфигурация и препроцессор. [Ограниченный hard-negative эксперимент](docs/xclip-hard-negative.md) не улучшил F1; baseline сохранён. [Подготовка будущего внешнего доступа](docs/external-access-preflight.md) готова локально, запуск отложен до отдельного решения после ответа ForteBank.

Следующий цикл завершён: [положительная ветка JPEG/PTS](docs/positive-evidence-plumbing.md) проверена синтетически; [spatial-ablation](docs/xclip-spatial-ablation.md) не улучшил качество; [Qwen action probe](docs/qwen-action-diagnostic.md) показал слабую правильность при корректном JSON. Новый классификатор типов не принят. Объяснения банковских видео из облачных чатов не открываются и не используются.

Локальный исследовательский прототип. Репозиторий готовится для локальной работы: без push, публичного сервиса, туннеля, постоянного API-ключа и отправки заявки.

## Подтверждённое состояние

UI и конкурсный HTTP-контракт проверены на искусственных MOV. Это не измерение качества модели. Лучший сохранённый сравнительный кандидат — XCLIP ordered-max: TRAIN group OOF, TN6 / FP6 / FN2 / TP12, F1=0.75. TRAIN повторно используется для исследований, автоматические группы не проверены человеком. Типы, юридическая применимость и релевантность кадров этим результатом не подтверждены.

Экспериментальный XCLIP API возвращает бинарное решение, кандидатный момент и исходные кандидатные кадры только локально. Тип явно `unverified`, правило `not_assessed`. Он не выдаёт эти записи за полноценный конкурсный результат. Текущий гибрид Qwen/R22 не допущен на TRAIN: полного отчёта предварительных контролей нет. Качество текущего XCLIP на TUNE/HOLDOUT ещё не измерено. Готовность к отбору не подтверждена.

Измерения: [XCLIP](docs/xclip-candidate.md), [claim ledger](docs/claim-ledger.csv). Оставшиеся требования: [чеклист](docs/local-readiness.md).

## Среда и тесты

На этом Windows используется Python3.12.11 в `.venv-patched`, версии зафиксированы в [requirements-patched-lock.txt](requirements-patched-lock.txt). Старая `.venv` сохранена для исторической воспроизводимости; новая inference-среда — `.venv-patched`. PyAV включает FFmpeg libraries.

```powershell
.\.venv-patched\Scripts\python.exe -m pytest tests -q
```

Кодовые тесты используют искусственные изображения/MOV и лёгкие процессы. Банковские видео и модели они не открывают. Тесты API требуют разрешённого loopback-контекста. В сетевой песочнице Codex127.0.0.1 может быть запрещён; не меняйте защиту ОС или firewall ради теста. [Надёжность выполнения](docs/execution-reliability.md).

Для новой машины с совместимым NVIDIA-драйвером:

```powershell
py -3.12 -m venv .venv-patched
.\.venv-patched\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cu130 'torch==2.14.1+cu130' 'torchvision==0.29.1+cu130'
.\.venv-patched\Scripts\python.exe -m pip install -r requirements-patched-lock.txt
```

Lock описывает работающую установленную среду. Чистая установка на другую машину здесь ещё не проверялась.

## Искусственное UI/API демо

```powershell
$env:CASH_API_KEY='temporary-local-ui-test-only'
$env:CASH_PRIVATE="$PWD\.private\synthetic-ui-service"
.\.venv-patched\Scripts\python.exe scripts/serve.py --synthetic-test
```

Откройте http://127.0.0.1:8765/ и введите временное тестовое значение вручную. Принимаются только сгенерированные файлы из `.private/synthetic`. Это демонстрация интерфейса и контракта, а не банковский детектор. UI без CDN и аналитики.

Конкурсный контракт: `POST /api/v1/analyze` (multipart `file`, MOV) и `GET /api/v1/jobs/{job_id}`. Оба требуют `X-API-Key`. Только `violation`/`no_violation`; технический сбой — `failed`. Экспериментальные поля в конкурсную схему не добавляются.

## Экспериментальный XCLIP API

Первое получение публичных весов требует сети; потом обработка использует локальные файлы:

```powershell
.\.venv-patched\Scripts\python.exe scripts/install_xclip.py
```

Проверяются официальная фиксированная ревизия, MIT-лицензия и SHA весов. Этот шаг не читает банковские данные. Повторная загрузка на текущей машине не нужна.

После замороженного TRAIN-эксперимента подготовьте приватные прототипы из готового TRAIN-кэша:

```powershell
.\.venv-patched\Scripts\python.exe scripts/prepare_xclip_experimental.py
.\.venv-patched\Scripts\python.exe scripts/run_xclip_experimental.py
```

Нового inference при подготовке нет. Приватный пакет не включается в Git. В чистом клоне он отсутствует: его построение требует разрешённых локальных данных и процедуры [XCLIP-PROTO-01](docs/xclip-candidate.md). In-sample deployment-fit метрика не вычисляется.

Запуск строго на127.0.0.1:8768 с фиксированным временным тестовым значением `temporary-xclip-experimental-only`, без создания credentials. Публично этот режим не выставлять.

```powershell
curl.exe -X POST http://127.0.0.1:8768/api/experimental/xclip/analyze -H 'X-API-Key: temporary-xclip-experimental-only' -F 'file=@new.mov'
curl.exe http://127.0.0.1:8768/api/experimental/xclip/jobs/JOB_ID -H 'X-API-Key: temporary-xclip-experimental-only'
```

В этом режиме `/api/v1/*` возвращает503. Маркер контракта запрещает подключать режим к хранилищу другого API до изменения заданий. [Подробности и ограничения](docs/xclip-experimental-api.md).

## Приватность, лицензии, Git

Исходники не меняются и не переименовываются. Имена, номера, порядок и готовые ответы не используются при inference. Загрузки получают непрозрачные job ID, результаты защищены ключом владельца. Банковские видео, кадры, описания и результаты отдельных видео нельзя открывать cloud-инструментами. Аудио и идентификация лиц не используются. Для скриншотов — пустой UI либо искусственный материал.

`.private`, модели, среды, таблицы, видео, кадры, кэши, локальные outputs и секреты исключены из Git. Оригиналы и приватные артефакты текущий процесс не удаляет. Перед будущей публикацией:

```powershell
.\.venv-patched\Scripts\python.exe scripts/audit_repo.py
.\.venv-patched\Scripts\python.exe scripts/audit_git_history.py
git status --short
```

Проверяются tracked/untracked и вся доступная история, запрещённые типы и известные маркеры секретов. Это не универсальное доказательство отсутствия любого закодированного секрета; нужен code review. Сейчас push и публикация отложены пользователем.

Собственный код — Apache-2.0. Для Microsoft XCLIP отдельно проверены MIT весов и upstream-кода; Transformers — Apache-2.0. [Лицензии](docs/licenses.md), [провенанс XCLIP](docs/xclip-candidate.md). Внешние данные разрешены FAQ7, но требуют отдельной проверки прав: [политика](docs/external-data-policy.md). Qwen/llama.cpp сохранены как исследовательские ветки, не принятый детектор.
