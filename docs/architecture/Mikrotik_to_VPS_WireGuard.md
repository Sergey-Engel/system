---
type: architecture
status: current-reference
updated: 2026-09-13
---

# MikroTik как клиент TimeWeb WireGuard

На Нахимова 11 используются три обычных WG-интерфейса:

| MikroTik | Endpoint TimeWeb | Назначение |
| --- | --- | --- |
| wg1 | 94.241.171.65:51820/UDP | Legacy Fornex через TimeWeb |
| wg-cenuta | 94.241.171.65:51850/UDP | Selector Cenuta через TimeWeb |
| wg-home | 94.241.171.65:51830/UDP | Обратный BTH-путь и выход через Дом.ру |

Источник описания: saved RouterOS after-export 13 сентября. Позднее получен свежий text export 16:02:58 UTC и проверен в backup, см. [VPN_Maintenance_and_Backup](<../operations/maintenance-and-backup.md>), без полного повторного аудита правил. [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>) содержит адреса, route tables, группы LAN и ограничения.

Smart Split выбирает группу `CENUTA_Devices` или `VPN_Devices`, учитывает Local/RU/forced/bittorrent исключения и порядок mangle. Это не тот же механизм, что REALITY user-routing на TimeWeb, и не прямой AWG31 на Fornex.

Добавление LAN-устройства в группу требует проверки точного IP/DHCP, исходного списка, действующего порядка правил и адресного обратного diff. Не создавать заново интерфейсы и default routes из первоначальных примеров.

[MikroTik_Quick_Guide](<../quick-start.md>): диагностика. [VPN_HLD](<overview.md>): полная архитектура. [TimeWeb_Client_Creation](<../operations/TimeWeb_Client_Creation.md>): ограничения старого WG helper.

Исходная инструкция осталась в старом хранилище как история; не переносилась и не является текущим набором команд для повторного применения.
