---
type: task-checkpoint
topic: mikrotik
system: timeweb
status: active
created: 2026-09-25
tags:
  - mikrotik
  - vpn
  - timeweb
---

## Mac Mini FLEX

- Новый профиль: `.local/clients/Sergey/MacMini/SOCKS-TW-FLEX-S-Mini.json`.
- Новая REALITY identity `macmini-socks-flex` и WG peer `10.50.50.41/32`.
- FLEX policy: table `414`, mark `0x41`, source priorities `243/244`, mark priorities `184/185`, nft guard `flex_macmini`. Общие Gateway/RU-direct наследуются, индивидуальные overrides доступны в fleet console.
- До изменения создан VERIFIED backup `.local/backups/timeweb/2026-09-25T054647Z_current-config/`. Предыдущие live-файлы сохранены в закрытом серверном staging `/root/timeweb-flex-macmini-stage/`.
- Проверены Xray candidate test, live `timeweb-flex-macbook --device macmini reconcile`, fleet `3/3 routes ready`, systemd timer, console и `BTH_CONTRACT_VALID` после обновления контракта.
- Индивидуальный `Gateway=FX` для Mac Mini подтвержден read-back; MacBook остался на Cenuta. Затем override возвращен к `Default`: Mac Mini снова Cenuta/RU-direct ON, `3/3 routes ready`; повторный BTH `--check` прошел.
- После внедрения создан VERIFIED backup `.local/backups/timeweb/2026-09-25T060542Z_current-config/`.
- Клиентский импорт и сквозной трафик не проверены. Полный JSON и ключи в Obsidian не хранятся.
