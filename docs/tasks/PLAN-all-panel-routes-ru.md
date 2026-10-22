# PLAN: Российские IPv4 Напрямую Во Всех Режимах Панели

Дата: 2026-10-21. Статус: Done. Разрешение: пользователь запросил
RU-direct по IP во всех режимах Device routing и соответствующие названия.
Scope: WG-Cenuta/Fornex, SSTP-Cenuta/Fornex и Direct обоих направлений;
не пересоздание пользовательских профилей, не BTH/management и не failover.

| Шаг | Задача | Статус |
| --- | --- | --- |
| 1 | Read-only сверка RU prefix sets, правил и сохранённых назначений | Done: исходное покрытие,8588 normalized CIDR, оба pinned serial |
| 2 | Policy/controller/UI, unit и негативные tests | Done:682 tests; desktop/mobile, все названия-RU |
| 3 | Fresh backups, scoped migration под lock, rollback и IP-пробы | Done: exact rollback, шесть RU/non-RU positive/negative probes, modes сохранены |
| 4 | Registry/masters, monitoring contracts/cycles, post backups | Done: fresh router/TimeWeb/local VERIFIED backups, 102 protected files unchanged, two fresh cycles, validator PASSED |

Российский адрес определяется IPv4 CIDR list, не доменом/языком сайта.
RU должен идти в main/местный WAN исходной площадки; non-RU через выбранный
выход и блокироваться при его отказе. Сохранить local/private доступ,
DNS guards, исходные device modes и точный вне-scope export. Перед внедрением
подтвердить route priority реальными изолированными пробами. При неизвестном
drift не обновлять baseline. IPv6 не объявлять покрытым IPv4 списком.

Границы приёмки: шесть изолированных router-originated positive/negative
проб, не проверка с устройств. Реальные LAN/Wi-Fi ingress, DNS/HTTPS/apps
и обрыв рабочего тоннеля не проверены. [Результат и backups](../history/2026-10-21-all-panel-routes-ru.md).
