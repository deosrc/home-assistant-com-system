# Pushover receiver

A Pushover receiver sends notifications through one configuration entry of
Home Assistant's [Pushover](https://www.home-assistant.io/integrations/pushover/)
integration. Com System offers one receiver for each Pushover entry (see
[automatic detection](README.md#automatic-detection)).

## Delivery

A notification is delivered by calling the entry's own
`notify.<name>` action, where the name is the one given when the entry was
set up (lower case, spaces as underscores), with the message and, when
given, the title. If that action does not exist (for example the Pushover
entry is not loaded) the delivery fails for that receiver only, with the
reason in the result.

## Supported content

| Content | Supported |
| --- | --- |
| `message` | Yes |
| `title` | Yes |
| `priority` | Not yet |
| `image` | Not yet |
| `data` | Not yet |

Priority will map to Pushover's priority and an image to its attachment.
Pushover's attachment must be a file in a folder listed in
`allowlist_external_dirs`, so an image given as a URL will need fetching
first.

## Person and area

Pushover has no link to a Home Assistant user, so the person is chosen by
hand: choose **Configure** on the receiver and pick the person. A Pushover
entry is one user's account, so choose at most one.

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
