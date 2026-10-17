# Проверенный checkpoint

ECC: C:\Users\gokusen\.codex\skills\ecc-windows-engineering. SKILL.md, architecture-and-build.md, security-and-release.md, quality-and-debug.md прочитаны. Это instruction-only adaptation без ECC runtime/hooks/самостоятельных агентов. В config.toml не найден профиль ecc-engineering; просмотренные hook state относятся к ponytail, здесь их не запускаем. Связанных AGENTS.md и .agents/skills в выбранном workspace и его проверенных предках не найдено. Файлы существующих проектов не редактировались.

Применённый процесс: DISCOVER → PLAN → IMPLEMENT → VERIFY → REVIEW → FIX → REVERIFY. Роли — последовательные перспективы текущего агента. Дополнительные агенты не запущены. Данные и смысловые результаты не передаются облачным инструментам.

Отдельный проект: forte-cash-review. Изолированные .runtime/.venv/.cache. Python 3.12.11 установлен локально. Исходные видео и labels не изменяются. Выбор PyAV wheel вместо сборки FFmpeg сохраняет ОС без компиляторов/изменения защиты.

FAIL первой установки: PyAV 14.4.0 не имел подходящего Windows wheel и требовал C compiler. Исправление: PyAV 16.0.1 готовый wheel. FAIL первого тестового запуска: sandbox TEMP не давал pytest создать каталог, исправляем явным basetemp внутри .private. Это ошибки среды проверки, не качество detector.

НЕ ПРОВЕРЕНО: публичный URL, производственный ключ, реальный holdout, реальная другая камера, ручная релевантность доказательств и классификация без локальных аннотаций. Не считать UI/API тесты доказательством качества модели.

PASS: синтетический интеграционный прогон `pytest -q --basetemp=.private/test-run-03`: 5 passed, 1 warning, 3.03s. Исправлена реальная гонка: done теперь публикуется после завершения worker, чтобы следующая загрузка не получала 429 после done. Проверены 401, 404 чужого ключа, 415, пустой/повреждённый файл, 429, async positive/negative synthetic, JPEG schema, PTS, прерванный job после рестарта. Warning — deprecated alias в установленном Starlette TestClient, не результат анализа.

Технический блокер следующего этапа: соединение Windows exec-server потеряно; новый exec возвращает transport disconnected / unknown session id. Статус загрузки больших weights/CUDA и получения полного закона после потери связи неизвестен. Никакого подтверждения готовности модели, публичного сервиса или реального baseline нет. Не повторять публикацию или запуск с неизвестным исходом без проверки состояния после восстановления.
