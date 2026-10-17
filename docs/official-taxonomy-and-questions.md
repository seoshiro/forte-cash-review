# Official taxonomy check and questions: draft, not sent

Checked the supplied full ForteBank brief/FAQ and the original local workbook without modifying it. FAQ A2 says binary verdict and point timestamp are supplied, not event type; B8 says there is no closed type list and training categories are not disclosed; B9 allows unseen test types. The brief asks teams to derive a justified catalogue from visual evidence and public Kazakhstan rules. A verified public normative corpus is not an expert mapping of these training labels to rules.

The workbook has one labels sheet and three fields: file identifier, nullable point timestamp text, binary target text. No type, rule, event interval, object/role, bounding-box or applicability/exclusion annotation was found. This is a schema check, not a claim about inaccessible updated materials.

The public [event page](https://datathon.com.kz/ru) and [schedule](https://datathon.com.kz/ru/schedule), read on 17 October 2026, contain general event information and no additional case taxonomy. Authenticated participant-portal updates and organizer chat messages were not inspected. No global claim that further materials cannot exist is made.

CSV schema disclosed only: claim-ledger.csv = claim, value, unit, sample, split, calculation, evidence_type, limitation. No per-video CSV rows are included or exported here.

## Ready text for the user to ask organizers

Здравствуйте! Уточняем трактовку уже предоставленного ТЗ/FAQ ForteBank. Закрытый список тестовых типов не запрашиваем; ролики, кадры и ответы внешних ИИ не прикладываем.

1. Публиковались ли после исходного ТЗ дополнительные официальные материалы с критериями наблюдаемых событий, ссылками на применимые пункты и исключениями либо экспертными пояснениями к тренировочной разметке? Если да, где участникам получить актуальную версию?
2. Как автоматическая проверка сопоставляет свободную строку type с ожидаемым событием при отсутствии объявленной таксономии: допустимы ли синонимы, свои названия и ссылка на проверенный пункт? Нужен ли какой-либо канонический формат названия?
3. Что именно означает выданный точечный таймкод: начало действия, характерный кадр или любой кадр подтверждённого эпизода? Может ли один размеченный ролик содержать несколько допустимых событий/таймкодов, не перечисленных в таблице?
4. У побайтово одинаковых положительных записей встречаются разные официальные точечные отметки. Могут ли обе быть корректными точками разных событий? Как учитывать это при внутренней оценке локализации и куда сообщать такие вопросы по разметке в разрешённом закрытом канале?
5. Для признаков бездействия какое подтверждение полноты наблюдаемого эпизода считается достаточным? Можно ли считать отсутствие действия установленным только при полностью видимой соответствующей операции, без вывода по одному кадру?
6. Если применимость публичного пункта зависит от типа кассовой операции или роли участника, какие допустимые визуальные либо официальные контекстные признаки считаются достаточными? Не хотим выдавать предположение о контексте за установленный факт.
7. Если binary-признак найден, но конкретный тип или применимость пункта не подтверждены, какой ответ совместим с обязательным JSON-контрактом? Понимаем, что третьего verdict нет; не хотим подставлять неподтверждённый тип или превращать техническую/содержательную неопределённость в no_violation.

Эти вопросы не отправлены автоматически. Не просим пользователя оценивать кассовые процедуры, пересказывать реальные ролики, передавать ответы GPT или самостоятельно исправлять официальные метки. Локальные предложения пользователя сохранены и исключены из обучения, prompts, выбора модели и оценки.
