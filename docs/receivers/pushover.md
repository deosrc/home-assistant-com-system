# Pushover receiver

## Integration

Sends notifications to one device (Pushover calls it a target) of an account
set up in Home Assistant's
[Pushover](https://www.home-assistant.io/integrations/pushover/)
integration. Com System asks Pushover which devices the account has and
offers one receiver for each. Only loaded entries are asked, so a device
appears once Pushover has started and can be reached.

## Features

- Priority, image attachments and Pushover's own options (sound, URL and
  more).
- Pushover has no link to a Home Assistant user, so the person is chosen by
  hand, and a device belongs to at most one person (see
  [person](../next-steps/person.md)).
- The receiver's entities get their own device. Give that device an area if
  area targets should reach it (see [areas](../next-steps/areas.md)).

## Notification parameters

| Parameter | Supported | Mapping |
| --- | --- | --- |
| `message` | Yes | `message` |
| `title` | Yes | `title` |
| `priority` | Yes | Mapped, see below |
| `image` | Yes, if an allowed local file | `attachment` |
| Other fields | No | Dropped, with a warning |

`priority` maps `low` to -1, `normal` to 0 (nothing is sent), `high` to 1
and `critical` to 2. Critical also sends `retry: 60` and `expire: 3600`,
which Pushover requires.

`image` must be a file in a folder listed in `allowlist_external_dirs`. A
`/local/...` path (the `www` folder) and a local media source
(`media-source://media_source/local/...`) are files. A URL or an entity is
not fetched: the image is dropped with a warning, as is a file that is
missing or not allowed.

`data` is the `pushover` block. It is passed to the action and overrides the
mapped values. Other keys are dropped with a warning.

| Key | Description |
| --- | --- |
| `priority`, `attachment` | Override the mapped values |
| `url`, `url_title` | A link shown with the message |
| `sound` | The notification sound |
| `html` | Format the message as HTML |
| `timestamp`, `ttl` | Message time, and how long it lives |
| `retry`, `expire` | For critical messages |
| `callback_url`, `tags` | Receipt callback and tags |

```yaml
action: notify.com_system
data:
  message: Door open
  priority: critical
  people:
    active_choice: Individuals
    Individuals: person.alice
  data:
    pushover:
      sound: siren
```

## Other information

A notification is delivered by calling the entry's own `notify.<name>`
action, where the name is the one given when the entry was set up (lower
case, spaces as underscores), with the device as its `target`. If that
action does not exist (for example the Pushover entry is not loaded) the
delivery fails for that receiver only, with the reason in the result.
