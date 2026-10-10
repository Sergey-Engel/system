## WSS-резерв для TimeWeb -> Fornex

Этот комплект добавляет **ручной** резервный транспорт для обоих выходов TimeWeb -> Fornex: существующего WireGuard `wg-relay/wg1` и userspace WireGuard outbound `wg-fornex` сервиса `xray-timeweb-reality`. Основной путь остаётся без изменений: UDP `103.75.126.143:51821`.

Резервные пути: `wg-relay/wg1 -> 127.0.0.1:51921/UDP -> mTLS WSS TCP/8443 -> Fornex 127.0.0.1:51821/UDP` и `Xray wg-fornex -> 127.0.0.1:51923/UDP -> тот же mTLS WSS carrier -> Fornex 127.0.0.1:51821/UDP`. Сервер WSS принимает только клиентский сертификат TimeWeb и ограничен единственным назначением `127.0.0.1:51821`.

### Операции

На TimeWeb:

```bash
sudo timeweb-fornex-wg-transport status
sudo timeweb-fornex-wg-transport backup
sudo timeweb-fornex-wg-transport native
```

`backup` запускает два WSS-клиента, проверяет оба UDP-listener и carrier-route через `eth0`, меняет runtime endpoint `wg1`, а затем атомарно обновляет только endpoint `wg-fornex` в Xray config с валидацией Xray и перезапуском сервиса. Ошибка Xray откатывает оба контура на native UDP. `native` сначала возвращает Xray на публичный UDP endpoint, останавливает оба WSS-клиента и лишь затем переводит relay на native UDP. Этот порядок не даёт аутентифицированному локальному WSS-пакету повторно обучить relay адресу `127.0.0.1:51921`. Статус сообщает оба endpoint; неполная смена имеет режим `partial`, который консоль считает недоступным.

Web-консоль не получает write-доступ к `/opt/timeweb-reality`. Для `backup` и
`native` она вызывает ограниченный dispatcher
`timeweb-fornex-wg-console-transport`, который запускает root oneshot unit
`timeweb-fornex-wg-transport@{backup,native}.service`. `status` остаётся
read-only и исполняется непосредственно контроллером.

После подтвержденной смены контроллер атомарно пишет выбранный режим в
`/var/lib/vpn-uplink-pilot/transport-state.json`. Exporter читает только этот
файл и публикует его для Grafana; HTTP-запросы Grafana не выполняют SSH, probe
или смену транспорта.

Автоматического переключения в этой версии нет. Перед включением `backup` оператор должен зафиксировать недоступность нативного UDP и оставить результат проверки в журнале эксплуатации. WSS/TCP создаёт дополнительный overhead; при признаках фрагментации отдельной задачей подбирается MTU `wg1`, но текущий MTU не меняется.
