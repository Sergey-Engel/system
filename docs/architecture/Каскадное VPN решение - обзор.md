---
type: overview
status: superseded
updated: 2026-09-13
---

# Каскадное VPN-решение: указатель актуальной архитектуры

Прежний документ смешивал общий проект с WARP, reverse proxy и установкой дополнительных панелей с реальной инфраструктурой. Эти компоненты не следует считать развернутой схемой TimeWeb.

Актуальная архитектура: [VPN_HLD](<overview.md>). В ней отдельно показаны:

- Обычный WG-клиент -> TimeWeb -> Fornex/Cenuta и RU/BTH по policy rules.
- AmneziaVPN REALITY -> TimeWeb TCP/443 -> встроенный userspace WG -> Fornex/Cenuta/BTH.
- Прямой AWG 3.1 -> Fornex UDP/46056, без TimeWeb.

Реальные конфиги и мастер-копии: [VPN_Configuration_Registry](<../registry/configuration.md>). План и незакрытые проверки REALITY: [TimeWeb_VLESS_REALITY_Architecture_and_Plan](<TimeWeb_VLESS_REALITY_Architecture_and_Plan.md>).

Исходный общий проект остался в старом архиве и не переносился. Его команды установки UFW/панелей/WARP не являются действующим deployment-runbook и не должны повторяться поверх нынешних хостов.
