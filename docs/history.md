# Notification history

Com System keeps a record of the notifications it sends, so the panel can
show them under [Recent](ui.md#recent). Each record has the notification's
content (title, message and any other content), the time, and the result of
every receiver: delivered, failed or skipped, with the reason and any
warnings about content a receiver dropped. Failures and skipped receivers are
recorded too. A call that matches no receiver is rejected and not recorded.

## Limits

History is capped by both **count** and **age**: a notification is dropped
when there are more than the count limit, or it is older than the age limit.
The defaults are the last 200 notifications and 30 days.

To change them, open **Settings > Devices & services > Com System**, choose
the **Com System** hub entry and then **Configure**. The new limits apply
straight away and nothing is reloaded.

## Storage

History is saved in Home Assistant's `.storage/com_system.history` file, so
it survives restarts. Each receiver's `notification_receiver` entity also
shows its own last attempt.
