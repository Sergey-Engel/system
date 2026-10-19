# PLAN: Нахимова → Фетхие через Direct SSTP

Статус: Done (клиентская приёмка Нахимова недоступна)
Создан: 2026-10-19

## Контекст

Пользователь поручил автономно подготовить обратное направление под ключ.
Используется существующий двунаправленный SSTP, без нового TLS/PPP соединения.
Подтверждение реального клиента в Нахимова недоступно и не подменяется
router-originated проверкой.

## Задачи

| Шаг | Задача | Приоритет | Статус | Зависимость |
| --- | --- | --- | --- | --- |
| 1 | Live конфигурация, строгие baseline, свежие private backups | P0 | Done | Нет |
| 2 | Отдельная обратная policy и контроллер, тесты безопасности | P0 | Done | 1 |
| 3 | Два направления в панели, независимые списки и ошибки | P0 | Done (local + live UI) | 2 |
| 4 | Ограниченный deploy, router-originated HTTPS/MTU/fail-closed | P0 | Done | 2 |
| 5 | UI/HTTP, регрессии, сохранение TimeWeb, masters и документация | P0 | Done | 3, 4 |

## Контракт

- Forward API и текущий Local MacBook сохраняются. TimeWeb не меняется.
- Нахимова: отдельная таблица `sstp_fethiye`, default через `sstp-direct-out`,
  резервный blackhole; включение только по MAC и закреплённому DHCP IP.
- Fethiye: узкие NAT/forward исключения только для `10.60.64.2/32` из SSTP
  в `ether1`, только публичные назначения. Никакого общего LAN-to-LAN доступа.
- Отдельный owner `s2s-sstp-reverse-v1`, состояние, revision и audit.
- Обычный выход Нахимова по умолчанию. Ни одно реальное устройство автоматически
  не переключается. DNS выбранного клиента идёт через SSTP; IPv6 закрыт.
- Строгая проверка обеих конфигураций учитывает зарегистрированные устройства
  обоих направлений. Неизвестный drift не принимается автоматически.
- Add требует проверенного транспорта и обоих роутеров; Remove доступен при
  проверенном source router даже при недоступном remote management.
- Никакого фонового обновления UI. Сообщение операции сохраняется до закрытия
  либо следующего действия. Выбор направления не смешивает устройства/revision.

## Приёмка и откат

Свежие private pre/post exports и encrypted backups; точный diff вне owner
должен отсутствовать. Положительный router-originated HTTPS, MTU и отрицательная
проверка отдельного reverse route без отключения общего SSTP. Временные объекты
удаляются с точным readback. Откат удаляет только новые reverse объекты и
восстанавливает согласованные локальные baseline, не транспорт или TimeWeb.

Открытых вопросов нет; отдельный клиентский тест остаётся непроверенным.

## Лог

Live serial/конфигурации сверены, MacBook Local; DHCP `defconf`/bridge на обеих
сторонах. Pre-backups обеих сторон VERIFIED_TRANSFER; TimeWeb contracts PASS.
Private evidence: `.local/backups/site-to-site/20261019T115624Z-sstp-reverse/`.
Новые проверки первоначально RED (отсутствие reverse API/policy); после
реализации полный набор 564 passed. UI проверяет два направления, разделение
списков/revision, Add/Remove, sticky errors и отсутствие таймерного refresh.

Final: 571 passed; repository validation468 public files/67 profiles/22 devices,
problems=[]; portable store VERIFIED. Router-originated HTTPS/DF1400,
reverse-only blackhole outage/recovery PASS, shared SSTP оставался up.
Счётчик Netwatch до первого замера проверяется на null; explicit disabled=no
нового route нормализован только после доказанного одиночного semantic diff.
SNAT `.88/24` ограничен public destinations. Два fresh collector cycles,
Prometheus, Grafana и runtime/BTH/monitoring contracts PASS без публикации policy.
Live desktop/mobile UI без page errors/POST/overflow, оба направления и VPN
доступны. Три online DHCP-клиента Нахимова, selected0; MacBook Local, state
не менялся. Sensitive exports/masters обновлены, post-backups VERIFIED_TRANSFER:
`.local/backups/site-to-site/20261019T121519Z-sstp-reverse-post/`.
Секреты и full evidence сохранены только в private/canonical store.
