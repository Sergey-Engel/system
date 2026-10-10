---
type: architecture
status: superseded
updated: 2026-09-13
---

# Back to Home: существующая схема

BTH уже развернут, не требует повторного создания `wg-home` или пересоздания Docker по старой инструкции.

Два клиентских входа используют домашний Internet-выход:

| Вход | Путь | Граница |
| --- | --- | --- |
| Прежний WG BTH | Клиент -> TimeWeb UDP 51830 -> wg-home -> MikroTik -> Дом.ру | Отдельные WG-профили, DNS в них 192.168.88.1 |
| REALITY BTH | Amnezia -> TimeWeb TCP 443 -> Xray WG source 10.30.30.5 -> wg-home -> MikroTik -> Дом.ру | Internet-only, private LAN заблокирована; внутренний DNS общий зарубежный |

Схема из нескольких routing tables не дает «100% изоляции» сама по себе. Реальная защита включает source/UID guards, порядок native nft/rules и recovery-контракт; полный reboot/fail-closed regression не закрыт.

- [VPN_HLD](<overview.md>): текущая схема размещения.
- [Current_Mikrotik_hAP_ax3_Config](<../hosts/nakhimova/Current_Mikrotik_hAP_ax3_Config.md>): последний сохраненный RouterOS after-state.
- [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>): действующий REALITY BTH.
- [TimeWeb_REALITY_Backup_and_Rollback](<../operations/TimeWeb_REALITY_Backup_and_Rollback.md>): зависимости и восстановитель.
- [TimeWeb_VPN_Registry](<../registry/tunnels.md>): обычные BTH и REALITY-профили.

Первоначальная инструкция осталась в исходном архиве и не переносилась. Команды create/recreate и общие правила из неё не повторять на действующем роутере/TimeWeb.
