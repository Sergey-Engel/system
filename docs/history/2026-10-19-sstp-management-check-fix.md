# Отказ SSH-Проверки Нахимова Перед Add

Дата: 2026-10-19. Исправление установлено в локальной панели19118.

## Наблюдения

После предыдущего исправления пользователь выбрал MacBookAir192.168.89.197.
Отказ теперь другой: `validated_direct_route_unavailable` до записи.
На скриншоте: Nakhimova unavailable or configuration requires review.

Отдельная read-only проверка воспроизвела отказ Nakhimova connect через11.35s,
одновременно Fethiye SSTP running=true, baseline совпадал. Внутри SSTP
10.60.64.2 ответил5/5, без потерь. Далее TimeWeb доступен, WG ping3/3,
прежний management TCP22 доступен. Три fresh подключения подтвердили
HKM0BDXYG74, исходный baseline и SSTP running=true. Низкоуровневая причина
исходного временного отказа не записана; DPI, потеря питания или падение
прямого SSTP не установлены.

## Исправление

Local `direct_access.connect`: максимум две попытки начального соединения
при timeout/EOF/SSH transport failure, с закрытием неудачного client/proxy.
Pinned known_hosts обязателен. Authentication, host key, serial и прочие
validation failures не повторяются и не обходятся. После установления SSH
повторы команд отсутствуют, в том числе при потере ответа на запись.

Статусы различают исчерпанный connection retry, configuration review и
ошибку read/identity validation. Unknown больше не окрашен зеленым.
Свежая проверка обоих baseline до Add сохранена. Автоматического выбора,
fallback маршрута, фонового опроса или изменения TimeWeb нет.

API и тайм-ауты проверены по
[Paramiko SSHClient](https://docs.paramiko.org/en/stable/api/client.html).
Новые зависимости, изменения ключей и сетевых служб не нужны.

## Проверки

- RED:5 failed /3 passed. Focused после расширения:34 passed.
- Полный набор: **543 passed**. Проверены transient retry, лимит двух попыток,
  отсутствие retry при authentication/host key/serial/missing pin/drift,
  отсутствие replay записи, отдельные статусы и блок Add при отказе управления.
- Пять fresh live проверок конфигурации и SSTP успешны. В первой специально
  внедрен локальный отказ первого connect до сети: повтор выполнил настоящий
  SSH с pin/serial/baseline validation. Всего Nakhimova connect6, проверок5.
- Реальный Add preflight MacBook192.168.89.197 прошел до первого `save`.
  `save` перехвачен только в отдельном проверочном процессе и остановил
  операцию; router mutate запрещен в этом процессе. Записей0, state hash
  не изменился. Это не приемка фактического переключения устройства.
- После restart только local `com.sergey.sstp-panel`: HTTP available=true,
  tunnel=up, error=null, selected0. Config/state SHA совпали с pre-edit снимком.
- Рабочий браузер1280x900/390x844: page errors0, overflow0, router actions0.
- Canonical private store VERIFIED:2599 files/344 records.

Private evidence: `.local/backups/site-to-site/20261019T111803Z-management-check/`:
pre-edit sources/config/state/audit, `read-only-recovery-proof.json`,
`macbook-live-add-dry-run.json`, `live-http-status.json`, live screenshots.

## Ограничение

Прямой SSTP data path не зависит от TimeWeb, но существующая SSH-проверка
Нахимова проходит через TimeWeb management proxy. Короткий retry не чинит
длительную недоступность этого пути. При двух отказах Add останется запрещен;
это намеренная защита, не разрешение использовать последний успешный snapshot.
TimeWeb/Deco/роутеры/SSH-forward не менялись. Текущая страница может прочитать
новое состояние кнопкой Refresh; принудительно страницу не обновляли.
