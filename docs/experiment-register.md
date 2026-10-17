# Реестр экспериментов

Holdout остаётся закрытым. Текущий TUNE уже использовался повторно; никакой внутренний F1 не называется независимым final результатом или официальным баллом.

BUDGET-01 был заменён на BUDGET-01R1 до первой модельной проверки: две регистрации, один исполненный кандидат, исходных candidate model/TUNE runs = 0. R1: 192/128 tokens, не более двух coarse events, обязательный exclusion status; unknown/present отбрасываются. Три TRAIN-пробы завершены со schema 3/3, TN/FP/FN/TP = 0/2/0/1. Quality gate провален, кандидат не принят, его TUNE не запускался. Отдельный loopback API QA измеряет техническую готовность этого кода, а не пригодность распознавания. Полный uniform TRAIN отменён; упоминания его очереди ниже являются историей прежнего плана.

Завершены три семейства гипотез CPU: window uniform→refine, video uniform→dense, raw sequence→centered sequence. Первые два дали по два TUNE-результата; третье — четыре (две feature variants × две стратегии). Итого восемь завершённых конфигураций на TUNE до текущего Qwen baseline. В centered experiment 4 C × 9 thresholds × 2 strategies × 2 variants = 144 TRAIN-OOF metric configurations, с 4 grouped folds. Эти 144 не являются 144 TUNE попытками. Сами feature/model варианты и скрипты сохранены отдельно.

Три Qwen варианта формата (320 tokens, compact 512, constrained frame-ID 512) проверялись на трёх TRAIN пробах и синтетике. Они считаются тремя инженерными вариантами вывода, не тремя доказанными улучшениями качества. Текущий uniform Qwen — девятая начатая конфигурация TUNE; затем тот же протокол применяется к TRAIN. До завершения каждого split quality aggregate не публикуется. Прерванный запуск отмечается явно, без превращения ошибок в no_violation.

До оценки нового кандидата записан BUDGET-01 в config/budget-protocol.json: один coarse pass с 8 кадрами, не более одного уточнения с 4 кадрами, ограниченные токены/разрешение/число событий и единое извлечение evidence за проход. Это одна новая архитектурная гипотеза и одно запланированное сравнение с uniform. Threshold 0.8 и проверенный нормативный реестр сохраняются. TRAIN-only техническая проверка допускает максимум одно исправление синтаксиса; TUNE применяется один раз к замороженному варианту. После неудачи нельзя незаметно продолжать перебор на TUNE.

Смена Torch runtime и опциональная NF4 — отдельные технические переносы с обязательным раскрытием дополнительного сравнения качества. Результаты разных runtimes нельзя смешивать и приписывать различие только temporal refinement. NF4 пока не установлена и не измерена. До неё требуются официальный Windows wheel, проверка SHA/лицензии/наличия подходящего CUDA kernel, затем synthetic/CUDA/model check и те же quality/latency measurements. Текущая оценка не меняется.

Цель полного API upload→done: максимум 240 секунд в проверенных случаях, абсолютный технический cutoff 295. Это цель, а не достигнутый результат. Для принятия кандидата требуются schema/evidence integrity, F1 не ниже baseline и FP не выше baseline на том же exploratory TUNE, локализация и измерение queue/upload/model/decode/evidence. Малый TUNE не доказывает статистическую non-inferiority.


QVT-01, 17 October 2026: official-label-only Qwen visual-encoder static/temporal heads, fixed 2-second PTS grid, grouped TRAIN OOF. Rejected; temporal TN/FP/FN/TP=0/12/1/13, static=2/10/1/13. Detailed aggregate evidence and pre-result duplicate-row protocol deviation: docs/qvt-results.md. TUNE not run; HOLDOUT closed. Non-expert potentially cloud-influenced manual proposals are quarantined, not read and not a completion prerequisite. No further feature work or random model sweep initiated.


XCLIP-PROTO-01: frozen MIT X-CLIP, group OOF on 26 unique TRAIN contents / 24 existing groups, all four ordered/repeated x max/persistence arms reported. Primary TN/FP/FN/TP=6/6/2/12, F1=.75, BA=.6786, point MAE8.75sec n12. Rejected: FN2 and no FP reduction from persistence. No TUNE/HOLDOUT inference. Source/cache verified. Full results, provenance and resource cost: docs/xclip-candidate.md. Participant deployment-chat ambiguity separately pending official clarification in docs/deployment-clarification.md; no key/tunnel/deploy created.
