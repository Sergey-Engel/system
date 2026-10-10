# Configuration Templates

Этот каталог содержит только схемы и ссылки на секреты, не готовые клиентские
конфигурации. Точные текущие файлы материализуются из
[локального secret store](../../.local/secrets.json).

Существующие клиентские файлы лежат в [.local/clients](../../.local/clients);
их безопасный каталог: [clients.json](../inventory/clients.json).
Свежие конфигурации серверов: [.local/config/hosts](../../.local/config/hosts).
Не создавать второй публичный каталог полных конфигураций.

LaunchAgents генерирует [setup_mac.py](../../scripts/setup_mac.py) из текущего
расположения checkout. Старые абсолютные plist не используются.
