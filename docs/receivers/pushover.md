# Pushover receiver

A Pushover receiver sends notifications to one device (Pushover calls it a
target) of an account set up in Home Assistant's
[Pushover](https://www.home-assistant.io/integrations/pushover/)
integration. Com System asks Pushover which devices the account has and
offers one receiver for each (see
[automatic detection](README.md#automatic-detection)). Only entries that are
loaded are asked, so a device appears once Pushover has started and can be
reached.

## Delivery

A notification is delivered by calling the entry's own
`notify.<name>` action, where the name is the one given when the entry was
set up (lower case, spaces as underscores), with the message, the device as
its `target` and, when given, the title. If that action does not exist (for
example the Pushover entry is not loaded) the delivery fails for that
receiver only, with the reason in the result.

## Supported content

| Content | Supported |
| --- | --- |
| `message` | Yes |
| `title` | Yes |
| `priority` | Yes, mapped (below) |
| `image` | Yes, as an attachment, if it is an allowed local file |
| `data` | Yes: the keys below, from the `pushover` block |

`priority` maps `low` to -1, `normal` to 0 (nothing is sent), `high` to 1
and `critical` to 2. Critical also sends `retry: 60` and `expire: 3600`,
which Pushover requires.

`image` becomes the `attachment` key, which must be a file in a folder
listed in `allowlist_external_dirs`. A `/local/...` path (the `www` folder)
and a local media source (`media-source://media_source/local/...`) are
files. A URL is not fetched: the image is dropped with a warning, as is a
file that is missing or not allowed.

The `pushover` block of `data` is passed to the action and overrides the
mapped values. Its keys are `priority`, `attachment`, `url`, `url_title`,
`sound`, `html`, `timestamp`, `ttl`, `retry`, `expire`, `callback_url` and
`tags`; others are dropped with a warning.

```yaml
action: notify.com_system
data:
  message: Door open
  priority: critical
  data:
    pushover:
      sound: siren
```

## Person and area

Pushover has no link to a Home Assistant user, so the person is chosen by
hand: choose **Configure** on the receiver and pick the person. A device
belongs to one person, so choose at most one.

The receiver's entities get their own device. Give that device an area in
Home Assistant if area targets should reach it. See [Targets](../targets.md).

## Example

```yaml
action: notify.com_system
data:
  title: Door open
  message: The front door has been open for ten minutes.
  people:
    active_choice: Individuals
    Individuals: person.alice
```
