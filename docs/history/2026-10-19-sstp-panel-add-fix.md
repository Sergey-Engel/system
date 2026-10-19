# SSTP-Панель: Исправление Add И Самообновления

Дата: 2026-10-19. Исправление установлено в локальной панели19118.

## Причина И Изменения

Журнал зафиксировал `device_list_changed_refresh_and_retry`: сравнение общего
DHCP snapshot отклонило Add до изменения состояния/роутера. Проверка включала
не только выбранный MAC, но и все прочие аренды, hostname и online-флаги.
Какое именно поле изменилось в исходном snapshot, журнал не сохранял.

Новый per-device revision проверяет MAC/IP/lease ID, generation сохраненного
выбора и baseline identity. Несвязанные DHCP-изменения не мешают выбранной
операции. Перед первой записью привязка проверяется повторно. Legacy общий
revision принимается только при точном совпадении со свежим общим snapshot.
Строгие проверки конфигурации, pending/read-back и ограничения маршрутов
сохранены.

Ошибка команды отделена от ошибки состояния тоннеля. Известные pre-write
отказы сообщают, что настройки не изменены; неопределенный результат записи
по-прежнему требует проверки сохраненного выбора. Диагностический журнал
и audit теперь вместе синхронизируются с canonical private store: проверка
выявила ранее не синхронизировавшийся `last-error.json` после отказа.

Таймеры Direct-вкладки удалены. Чтение только при открытии вкладки, явном
Refresh и после явной команды пользователя. Ошибка остается до dismiss
или следующей команды; Refresh ее не скрывает, dropdown сохраняет выбор.
Время проверки видно рядом со статусом. Отдельная исходная VPN-вкладка
и серверные TimeWeb-компоненты не изменены.

## Доказательства

- RED: воспроизведены отсутствие per-device revision, подмена status-error
  сообщением операции и отсутствие checkpoint диагностического журнала.
- Полный набор: **531 passed**. Отдельно проверены смена IP/lease/generation,
  offline, повторная смена binding до write, отсутствие записей при отказе.
- Playwright fixture: Add с отказом,65s без повторного чтения, сохранение
  ошибки после Refresh, dismiss, успешные Add/Remove в fixture. Проверены
  per-device revision в запросе, VPN tab, desktop/mobile, отсутствие ошибок.
- Рабочий HTTP: новая разметка/Refresh, SSTP up/available, два устройства,
  выбранных0. Заведомо неверный revision отклонен до write с понятным
  operation_error, при этом status error=null. Config/state SHA256 совпали
  со снимком до restart, generation6. Реальный Add ноутбука не повторялся.
- Рабочая страница в отдельном headless браузере:1280x900/390x844,
  без горизонтального overflow и page errors, router actions0.
- Canonical private store: VERIFIED,2599 files/344 records.
- Точечный restart только `com.sergey.sstp-panel`; SSH-forward,
  TimeWeb и настройки обоих роутеров не менялись.

Приватный снимок config/state/audit до restart, candidate sources,
HTTP-отчет и live screenshots:
`.local/backups/site-to-site/20261019T104300Z-panel-add-fix/`.
Fixture screenshots: `.local/runtime/pytest-add-fix-release/`.
Ни restore, ни reboot не выполнялись. Уже открытая страница использует
прежний JS до однократной ручной перезагрузки; принудительно ее не обновляли.
