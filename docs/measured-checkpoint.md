# Измеренный checkpoint — CPU baseline и проверенный норматив

## Что действительно работает

Отдельный проект, read-only исходники, manifest/split, синтетические API integration tests и headless Edge UI QA. Проверены H.264 playback, реальные JPEG из искусственного ролика, таймлайн, desktop/mobile, ошибка ключа и processing failure. Исправлен общий deadline: отсчёт и резервирование capacity теперь начинаются до multipart parsing. Эти проверки не доказывают качество распознавания.

Модель DINOv2-small скачана с официальной model card Apache-2.0, SHA256 проверен. Ревизия/хеш в models/dinov2-small/provenance.json (не публикуются вместе с весами). CPU inference выполнялся с local_files_only и process-local network deny. Источники: https://huggingface.co/facebook/dinov2-small и https://github.com/facebookresearch/dinov2/blob/main/LICENSE .

## Результаты

Qwen uniform TUNE завершён 17.10: 9/9, технических ошибок 0. TN/FP/FN/TP = 0/4/0/5; precision 0.555556, recall 1, F1 0.714286. Все 9 verdict положительны; это совпадает с постоянным положительным контролем и не демонстрирует полезной specificity. Baseline сохранён как отрицательный результат, полный TRAIN отменён по последующему указанию пользователя.

Время engine.analyze: mean 384.8838 s, p50 392.063 s, p90 421.916 s, p95 427.216 s, max 432.516 s; 8/9 превышают 300 s. Upload, queue и one-time model load 22.39 s сюда не включены. Таймкод MAE 3.9134 s по 5 бинарным TP; это не оценка релевантности evidence или правильности типа. Полный официальный API SLA не пройден. Источник .private/structured/tune-uniform.safe-summary.json; численные claims воспроизводит ledger. Holdout закрыт. После TUNE выполняется один TRAIN технический профиль стадий, затем заранее записанный BUDGET-01, без второго GPU workload.

Расчёты .private/cpu-baseline/safe-summary.json, .private/video-baseline/safe-summary.json и .private/baseline-audit/safe-summary.json. Числа для использования только из docs/claim-ledger.csv. Train — in-sample, tuning — повторно используемая exploratory проверка; это не официальный балл и не final holdout.

| Метод | Split | TN / FP / FN / TP | Precision | Recall | F1 | MAE таймкода, с |
|---|---|---|---|---|---|---|
| Window uniform | Train | 13 / 0 / 0 / 14 | 1 | 1 | 1 | 3.64 |
| Window refine | Train | 12 / 1 / 0 / 14 | 0.933 | 1 | 0.966 | 2.21 |
| Window uniform | Tune | 1 / 3 / 5 / 0 | 0 | 0 | 0 | не определяется: нет TP |
| Window refine | Tune | 1 / 3 / 5 / 0 | 0 | 0 | 0 | не определяется: нет TP |
| Video uniform | Train | 13 / 0 / 0 / 14 | 1 | 1 | 1 | 6.64 |
| Video dense | Train | 13 / 0 / 0 / 14 | 1 | 1 | 1 | 6.07 |
| Video uniform | Tune | 2 / 2 / 5 / 0 | 0 | 0 | 0 | не определяется: нет TP |
| Video dense | Tune | 2 / 2 / 5 / 0 | 0 | 0 | 0 | не определяется: нет TP |

CPU extraction mean 3.60 s/video, max 9.31 s/video; load 0.453 s; RSS 535.6 MiB. Это отдельный batch feature benchmark, не полный API upload→done. Парное сравнение качества использовало общий dense feature cache; postprocess time не заменяет neural/end-to-end время. Уточнение не дало улучшения на tuning. Модель сильно переобучена и не используется как готовый юридический detector.

## Утечки и независимость

Только изображения→embeddings→статистика последовательности являются признаками. SHA256 служит ключом private cache, имя/ID/номер файла/порядок строк не подаются classifier. TRAIN timestamp используется как weak supervision; TUNE target/time — только для расчёта ошибок. Проверка original/renamed TRAIN дала одинаковые features/prediction, исходный checksum не изменился; row-order invariance подтверждена. Результат содержит только booleans в .private/baseline-audit/invariance.json.

Точных уникальных SHA256 — 40, предварительных групп — 38; групп по split — 24 train / 8 tune / 6 holdout. Найденные exact/near duplicates не пересекают split. Нельзя утверждать, что все соседние дубли/семейства сцен исключены: нужна локальная human review без cloud screenshots. Holdout не открыт, его features не использовались.

## Норматив

https://adilet.zan.kz/rus/docs/V1900019680 — постановление Правления НБРК №231 от 29.11.2019, регистрация №19680. Полный официальный текст получен по UUID c4cd4052-63e3-475b-ba9e-93f23de13fdb. История https://adilet.zan.kz/api/documents/c4cd4052-63e3-475b-ba9e-93f23de13fdb/versions помечает этот UUID is_current=true. В истории revision_date=2026-07-11T18:00:00.000Z; текст включает изменения, действующие с 12.07.2026. Database updated_at/end_date не трактуются как дата принятия/отмена акта.

Сверены и сохранены offline в config/rules.json: п.20 (приём/пересчёт при клиенте и хранение ранее принятых денег), п.22 (не покидать рабочее место до окончания обслуживания), п.31 подп.4 с исключениями п.32 (выдача и пересчёт), п.42 (внутренний пересчёт/сортировка/упаковка при контролирующем работнике, кроме приёма/выдачи клиенту). Признаки и исключения заданы отдельно; невидимое не считается доказанным. Из п.31 в model context включён только подп.4; идентификация личности/подписи исключены.

## Следующее

После восстановления сети сохранён code-only checkpoint df898ec. Дозагрузка продолжена из прежних partial, без второго экземпляра модели; helper проверяет точный HTTP Content-Range и полный SHA256. Тесты на синтетических байтах: resume с неполного префикса, отказ при HTTP 200 вместо 206, обнаружение неправильного SHA завершённого файла. Расчёт памяти по safetensors header — только BF16 tensor bytes, а не замер VRAM.

Дополнительная гипотеза DINO: вычитание среднего appearance внутри ролика для уменьшения зависимости от сцены. C и threshold выбирались только через grouped CV на TRAIN; затем единожды применялись к тому же exploratory TUNE. На TUNE raw и centered варианты дали TN/FP/FN/TP = 2/2/5/0, F1 = 0, как с uniform, так и с refine. Гипотеза не подтвердилась. Постоянный положительный прогноз добавлен только как контроль, не как detector. Вывод: не продолжать выдавать DINO proposal за пригодный сервис. Источник: .private/centered-proposal/safe-summary.json; все числа переносятся в claim ledger. Holdout не читался.

Локальный человек может открыть адрес из .private/local-review-url.txt для train/tune аннотаций. Просмотрщик слушает только loopback и требует временный token; cloud browser/vision/capture для него запрещены. Ручные категории, релевантность evidence и полная проверка семейств сцен пока не выполнены.

Qwen и CUDA artifacts завершены с проверкой официальных SHA256; установлен torch 2.8.0+cu128. Исходный VLM pipeline остановился на проверке структуры. Первый benchmark дал 0/3 валидных TRAIN observations; компактный prompt — 1/3, с двумя time_outside_window. Эти ошибки не являются F1 обнаружения. Подробности и границы измерений: docs/model-output-contract.md. Новый constrained decoder прошёл синтетическую генерацию и три unit-теста; полный набор — 26 passed. Текущий последовательный процесс scripts/run_structured_validation.py выполняет повторный benchmark, затем uniform TUNE и TRAIN только при валидной структуре. Status: .private/structured/status.json. Не запускать второй GPU workload и не менять runtime до окончания. Holdout закрыт.

Слабый CPU baseline не является пригодным продуктовым fallback. При медленной сети сохраняем API/UI и подготовленные проверки; не выдаём его F1 за качество VLM. До измерения VLM не заявляем готовность конкурсного анализа. Внешний доступ только подготовлен в docs/public-access.md. Постоянный API-ключ и публичный relay ещё ждут прямого разрешения. Submission не отправлен.
