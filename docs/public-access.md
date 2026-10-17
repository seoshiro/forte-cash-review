> Latest authorization: the user explicitly approved a free Cloudflare tunnel to this service and a separate permanent jury key at 2026-10-17 22:02:55 UTC. Prior pending/awaiting-bank wording below is historical and superseded. Execution still depends on local readiness and security preflight; no tunnel/key exists yet. Keep secrets local, use no paid features, do not submit the form. A repository is requested after completion; default private after publication audits. The reported bank approval is user-reported, not a verified organizer quotation.

# Бесплатный внешний доступ — подготовка, запуск не выполнен

Кандидат: Cloudflare Quick Tunnel к тому же локальному API/UI. Официальная документация: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ (проверена 17.10.2026). Временный trycloudflare.com URL, без аккаунта и домена; адрес живёт только пока работает cloudflared. Это demo/dev механизм без гарантии uptime, адрес меняется после нового запуска. API polling подходит; SSE не используется. Email browser authentication не добавлять: жюри использует неинтерактивный X-API-Key API.

Подготовленная команда ПОСЛЕ разрешения на публичное включение:

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

Один tunnel forward только к приложению, никакого filesystem/static forwarding исходного датасета. UI, загрузка, jobs и evidence остаются под собственным API auth. Работа моделей и хранение загрузок остаются на Windows. HTTPS-трафик проходит через Cloudflare relay; провайдер транспорта является отдельной стороной, это нужно явно согласовать перед передачей материалов жюри. Cloud AI inference не используется.

Не нужны firewall/router changes, открытый inbound порт, VPN, Windows service, автозапуск, OAuth grant или создание аккаунта. Не делать tunnel login, service install, named tunnel или изменения существующего cloudflared config. Если локальная установка/config мешает Quick Tunnel, сначала сообщить точное препятствие; не переименовывать чужую конфигурацию.

Отдельно ожидаются прямые подтверждения:

- создание постоянного серверного API-ключа непосредственно перед действием; в чат/публичный код его не печатать;
- запуск публичного внешнего канала и использование Cloudflare как relay; до разрешения остаётся только loopback synthetic;
- любые новые постоянные grants либо network/security changes требуют дополнительного отдельного разрешения. Защиту ОС не менять.

Перед активацией: готовая модель с измеренным временем, private jobs/auth checks, checksum официального cloudflared binary и проверка его --help; code-only Git audit. Наличие программы ещё не проверено, binary не скачивался и не запускался этой подготовкой. После разрешения — публичный synthetic upload→job→done, негативные auth/error checks и затем локальная проверка inference на разрешённых данных без cloud capture. Успех local health не означает доступность извне.

Ограничения: стабильность питания/интернета/процесса, меняющийся hostname и отсутствие uptime guarantee. После рестарта повторно проверить весь внешний путь и обновить адрес по разрешённому каналу. Запасной вариант не настраивать скрытно: сначала повторить разрешённый Quick Tunnel; если транспорт недоступен, сообщить blocker. Не покупать домен/хостинг, не создавать скрытую платную инфраструктуру.
