# Диагностика на искусственном входе

Источник: scripts/diagnose_synthetic_semantics.py. Только восемь копий RGB-фона (127,127,127), 384×384, созданных PIL. Скрипт не читает manifest, labels или видео. Одна загруженная BF16-модель на последовательность сравнений; локальный network deny. TUNE/holdout закрыты.

| Проверка | Наблюдение |
|---|---|
| Свободное описание без правил | 64-token cap; ответ содержит gray/grey/blank/solid/uniform/empty, не содержит проверяемых person/cashier/banknote keywords. Лексический sanity check, не автоматическая оценка всех утверждений |
| Короткий person yes/no | NO, отрицательный sanity пройден |
| Constrained boolean person_visible | false, отрицательный sanity пройден |
| Исходный доменный prompt + events schema | Два raw и два qualifying events на пустом фоне, провал |
| Тот же доменный prompt без constraint | Достигнут cap 192 токена; fenced и незавершённый JSON, strict format не пройден. Его нельзя объявлять ни верным отрицательным ответом, ни доказательством исключительной вины constrained decoding |

Во всех пяти случаях проверены batch=1, единственный user prompt и assistant generation suffix, отсутствие предыдущего assistant response, неизменность prompt prefix в generation, единственный output и декодирование только suffix после input length. Echo role tokens не обнаружено. Доменные input hashes в constrained/unconstrained совпадают.

Input audit: восемь vision_start/end, 968 image tokens соответствуют восьми grid [1,22,22] при merge=2; video tokens=0 ожидаемо для списка изображений. Pixel tensor [3872,1536], float32, все значения конечны и равны −0.003921568859; std=0 для однородного серого входа. Attention mask [1,1125] из единиц для свободного prompt. Конкретный input length зависит от текста вопроса.

Фактические классы Qwen3VLForConditionalGeneration / Qwen3VLProcessor. В официальном safetensors 625 tensors, из них 315 с visual prefix; зарегистрированные параметры находятся на cuda:0. Это вместе с простыми отрицательными ответами не подтверждает общий сбой vision-пути. Качество сложного действия этим не доказано.

Короткий доменный boolean gate без массива событий также вернул false на том же пустом входе; generation 3.078 s, model load 23.594 s отдельно. Его input/decoding audit прошёл. Это диагностическая гипотеза о влиянии формы задачи, а не принятый detector или новое качество на реальных роликах. Проверки не исключают always-negative поведение на сложных входах. До нового TUNE необходим ограниченный TRAIN-only контроль положительных и отрицательных случаев с фиксированным протоколом; holdout закрыт.

Причины менять модель по результатам базового vision sanity пока нет: свободная подача и короткие решения работают на пустом входе. Следующая проверяемая гипотеза — разделить решение о наблюдаемом событии и его последующее описание. Нельзя обещать улучшение recall, specificity или локализации до измерения. Новые веса не скачивались. Обновление security runtime остаётся отдельным техническим переносом и не должно смешиваться с оценкой этой гипотезы.

Реализация сверена с официальным [Qwen3-VL usage](https://huggingface.co/docs/transformers/model_doc/qwen3_vl) и [LMFE tokenizer adapter](https://github.com/noamgat/lm-format-enforcer/blob/main/lmformatenforcer/integrations/transformers.py). Документированный trim generated_ids[len(input_ids):] соответствует используемому срезу; tokenizer-data adapter использует тот же decode-after-zero и исключение special IDs. Не включаются удалённые kernels/trust_remote_code.
