# Com System – Home Assistant Custom Integration Plan

> Status: **Draft v0.1** – planning only, no code yet. This file is the
> source of truth for the design of work not yet built, the basis for the
> GitHub issues, and the context document for AI-assisted implementation.
> Built features are removed from it (see section 7). Sections marked
> **TBD** are intentionally unresolved.

## 1. Overview

Com System is a **notification distribution system** for Home Assistant,
built as a custom integration. It uses a **publish/subscribe** model:

- **Notification Receivers** are the subscribers. Each one represents
  something that can receive a notification.
- A notification is **published** by calling the `notify.com_system` action
  provided by this integration.
- Com System decides which receivers the notification applies to (based on
  the target parameters) and delivers it to them.

The integration does not replace existing notification mechanisms. It sits in
front of them and routes notifications to the right ones.

## 2. Concepts

### 2.1 Notification Receiver

A Notification Receiver is a configured endpoint that can be triggered by COM
System. There are two kinds:

1. **Built-in receivers** for existing Home Assistant services and entities
   that can already receive notifications (e.g. `notify.*` services and
   notify entities, mobile app notify targets).
2. **Custom receivers** which are Home Assistant scripts
   (scripts); built, see `AGENTS.md`.

Each receiver needs (details **TBD**):

- A unique name/ID.
- The mechanism used to deliver to it (an existing service/entity, or a
  user-defined action mapping).
- Association data used for target resolution: which **people** and/or
  **areas** it relates to (section 2.7).

**Storage, discovery and settings:**

- Com System uses **one hub config entry** and **one config entry per
  receiver** (top-level entries, not subentries). Receiver entities are
  created by each receiver's own entry.
- The **hub** entry is created once by the user. It holds the
  integration-level settings (an options flow; initially the history
  retention limits). One hub is enforced in the config
  flow; the manifest does not use `single_config_entry`, which would block
  receiver entries. The user flow creates the hub if none exists, and once
  one exists it becomes "add a custom receiver".
- Integration-level parts (history store, the
  `notify.com_system` action, the websocket API and the panel) are set up
  once in the integration's `async_setup`, not per entry, so receiver
  entries can load in any order and without the hub. Settings are read at
  use time, so changing them does not reload receivers.
- Removing the hub removes the receiver entries it created (core offers no
  confirmation hook, see the spike #6 decisions below); removing a receiver
  entry removes only that receiver.
- When the underlying device or integration is removed, the receiver is
  kept (built, see `AGENTS.md`). Its entities must show **unavailable**,
  keeping the receiver's conditions and settings. Deliveries to an
  unavailable receiver fail with a clear per-receiver result.
- Disabling a receiver's config entry removes its entities, so the
  documentation tells users to use the enabled switch (section 2.4); a new
  receiver's switch starts **on**.

**Spike #6 decisions** (verified with Home Assistant 2026.10.4; the feature
that builds on this removes it from the plan):

- **Attaching to another integration's device:** a device belongs to a single
  config entry and identifiers are unique per entry, so returning another
  integration's identifiers from `device_info` creates a **second** device
  (no area, no sharing). Instead, the receiver's entities set
  `self.device_entry` to the existing device (found with
  `async_get_devices(identifiers=...)`, using the source identifier stored in
  the receiver entry's data) and return no `device_info`. The entity
  registry then points at that device, so its area applies. Pre-creating the
  entity registry entry with a `device_id` does **not** work: the entity
  platform resets it to `None`. For types with no device, `device_info` with
  `(com_system, entry_id)` registers the receiver's own device.
- **Source removed:** removing the source integration deletes its device (our
  entry is not an owner) and the entity registry clears our `device_id`; the
  entities and the receiver entry remain. Availability is computed from
  whether the source device still exists, refreshed on device registry
  update events. When the device returns it is a new device, and our entities
  re-attach only when the receiver entry is **reloaded**; the hub's detection
  already reloads such receivers (see `AGENTS.md`).
- **Isolation:** an update listener that reloads only its own entry means
  editing one receiver leaves others untouched. Disabling a receiver's config
  entry does not remove its entities: they stay as `unavailable` (restored)
  with `disabled_by` set to the config entry, and other receivers are
  unaffected. This does not change the advice to use the enabled switch.
- **Hub removal cascade:** `async_remove_entry` on the hub can remove the
  receiver entries (schedule `config_entries.async_remove` as tasks) and
  their entities go with them. Core gives an integration **no hook to ask
  for confirmation** on removing an entry, so "after the user confirms" is
  not possible with the standard delete dialog; the documentation and the
  hub's title must warn that removing the hub removes all receivers.
- **Setup order:** `async_setup` runs once however entries load, so receiver
  entries load with or without the hub and in any order.

### 2.3 Message parameters

The `notify.com_system` action parameters fall into two groups:

1. **Target parameters** – described above.
2. **Content parameters** – describe what the notification says and how it
   behaves once delivered.

Content parameters are split into two tiers:

- **Common content** – supported by every receiver type: **`message`**
  (required) and **`title`** (optional). Receivers that have no title
  concept fold it into the message. Everything else, including priority and
  images, is receiver-specific.
- **Receiver-specific content** – only meaningful for certain receiver
  types, e.g. actions (buttons) on mobile app notifications. It is expressed
  in two ways:
  - **Typed fields** – commonly used parameters (used by several receiver
    types, or common in notification content) are explicit, validated
    top-level fields in the action schema. Receivers that do not support a
    typed field handle it as described under unsupported content below.
    Initially the typed fields are **`priority`** (a normalised urgency
    level that each receiver type maps to its own mechanism) and **`image`**
    (an image URL or media reference).
    - `priority` accepts `low`, `normal` (the default), `high` and
      `critical`. How each receiver type maps them is documented per type.
    - `image` accepts an http(s) URL, a local `/local/...` path or a media
      source ID. Camera entities are deferred.

    Others such as actions and sounds start in `data` and can be promoted
    to typed fields later if they prove widely used.
  - **Free-form `data`** – anything Com System does not support explicitly
    goes in a `data` object keyed by receiver type, e.g.
    `data: {mobile_app: {...}, pushover: {...}}`. Each receiver reads only
    its own block, so one notification can carry settings for several
    types. (Keying by type is an assumption from "mixed per-type blocks and
    typed fields"; to be confirmed.)

**Action responses:** each Com System notification is given an ID. When a
user responds to a notification action (e.g. presses a button on a mobile
app notification), Com System fires a `com_system_action` event (name
provisional) containing the notification ID, the receiver and the chosen
action, so automations can trigger on it. The response is also stored
against the notification in history, so the UI can show which receiver or
person responded. How each receiver type's native response event is mapped
to this event is documented per type. Responses from a type that has no
native response mechanism are not possible.

**Unsupported content:** when a notification carries content that a
resolved receiver does not support (e.g. mobile app actions sent to a
persistent notification), the notification is still delivered with the
content the receiver does support. The unsupported content is dropped and a
**warning is logged**. Warnings are recorded with the notification's
delivery result so they can be shown in the Com System UI (recent
notifications and the testing tool). Delivery is not treated as a failure.

### 2.4 Receiver entities and enabled state

The entities themselves are built (see `AGENTS.md` and
`docs/receivers/README.md`). What remains:

- **Source device:** types that attach to another integration's device
  implement `ReceiverType.source_device_identifiers`; reloading receivers
  whose source device reappears is the hub detection's job.

### 2.5 Supported receiver types

Initially supported receiver types, in priority order:

| Priority | Receiver type | Notes (to be verified) |
| --- | --- | --- |
| 1 | Mobile app | Core; per-device notify actions; rich content |
| 3 | Persistent notification | Core; HA UI notification area |
| 4 | Pushover | Core; priority, sound, attachments |
| 5 | webOS TV | Core; on-screen toast notifications |
| 6 | Music Assistant | Announcements via its own actions |

Each type needs a receiver-type definition (names provisional) covering:

- How receivers of that type are configured.
- Which common and receiver-specific content parameters it supports
  (section 2.3), i.e. its capabilities.
- How a Com System notification is translated into the underlying Home
  Assistant action call.
- How its receivers are associated with people and areas (section 2.7).

**Delivery per type:**

- **Mobile app** – built for message and title (see
  `docs/receivers/mobile-app.md`). Still to do: data (actions, image,
  channel and so on).
- **Pushover** – one receiver per device (target) of each Pushover entry;
  built for message and title (see
  `docs/receivers/pushover.md`). Still to do: `priority` maps to Pushover
  priority (-1/0/1/2, with `retry` and `expire` for 2), `image` to the
  `attachment` data key (a local file path that must be in
  `allowlist_external_dirs`, so a URL or media reference needs resolving to
  a file first), and other options (sound, URL) go in `data`.
- **Music Assistant** – one receiver per Music Assistant player. Delivery calls
  Music Assistant's announcement action rather than a notify action (the message
  is spoken; options such as an announcement URL or volume go in `data`). How a
  notification is delivered is an implementation detail of each receiver type's
  definition, so non-notify actions need no special handling in the receiver
  model. Players are shared devices with no person; the area comes from the
  device registry.

Receiver type definitions are written in code, and each declares its
capabilities: which typed fields and `data` keys it supports. The custom
receiver (built) remains the fallback for anything not on this list.

### 2.6 Notification conditions

Each receiver can be configured with **notification conditions**. They
decide, per notification, whether that receiver is used.

- Conditions use Home Assistant's built-in conditions system (the same
  format as automation and script conditions, including template, state,
  time and logical `and`/`or`/`not` conditions).
- Each condition is evaluated with these variables:
  - `notification` – the notification details: ID, title, message,
    priority, image, `data` and the requested targets.
  - `receiver` – the receiver's own context: name, type, associated person
    and area, and entity ID.
  - `resolved_targets` – why the receiver matched: which person, area or
    explicit target selected it.
- Exact field names within these variables are **TBD** and will be
  documented in `docs/conditions.md`.
- If the conditions do not pass, the receiver is skipped for that
  notification only. This is separate from the receiver's enabled state
  (section 2.4), which blocks all notifications.
- Example: skip a receiver when the notification message contains some
  given text, using a template condition on the notification variable.
- A receiver with no conditions always passes.
- Conditions are stored and edited **per receiver only**, as part of its
  config entry's options. There are no global or shared condition sets.
- If a condition errors (e.g. a template fails to render), it is treated as
  not passed: the receiver is skipped, the error is logged, and the result
  is recorded as skipped (condition error) in history, the entity's last
  result and the testing tool. This fails safe for rules such as
  do-not-disturb.

Evaluation order for a notification:

1. Resolve targets to receivers (`docs/targets.md`).
2. Drop receivers that are disabled (section 2.4).
3. Drop receivers whose conditions do not pass.
4. Deliver to the remaining receivers.

### 2.7 Associating receivers with people

Targeting by person needs a way to decide which receivers belong to
whom. Each receiver type provides an association mechanism (part of the
receiver type definition, section 2.5). Person associations can be
overridden manually on any receiver and are stored as part of the receiver's
own configuration. The mobile app mechanism is built (see
`docs/receivers/mobile-app.md` and `AGENTS.md`).

A receiver is associated with **at most one person**. A device used by
several people is treated as shared (see below) and reached through areas or
explicit targets.

**Other receiver types:** the mechanism is TBD for each. For example, TVs
are likely to be associated by area rather than by person. Pushover is
associated with a person manually (built), and Echo devices (built) by area,
with a person only set manually.

## 3. The `notify.com_system` action

The action, dispatcher and per-receiver response are built; see
[docs/services.md](docs/services.md) and `AGENTS.md`. What remains:

- Resolved receivers whose **conditions** do not pass are dropped before
  delivery and reported as skipped (section 2.6).
- The content parameters of section 2.3 (`priority`, `image`, `data`) are
  added to the schema, and unsupported content produces warnings.
- Failures are also recorded in history (section 5).
- Not verified: how the action renders in a real frontend (only the
  websocket description was checked).

## 4. Architecture (initial outline)

Proposed layout following Home Assistant custom integration conventions
(domain `com_system`):

```text
custom_components/com_system/
  __init__.py       # setup / unload, registers the notify action
  manifest.json
  config_flow.py    # config + options flow, receiver management
  const.py
  notify.py         # notify.com_system action
  dispatcher.py     # per-receiver delivery
  notification_receiver.py  # read-only receiver entity (new domain)
  switch.py         # enabled switch entity
  services.yaml / strings.json / translations/
  websocket_api.py  # commands backing the UI
  frontend/         # panel source and build output (TBD)
tests/
```

Core components (names provisional):

| Component | Responsibility |
| --- | --- |
| Receiver entities | Enabled switch and read-only `notification_receiver` |
| Condition evaluator | Runs a receiver's conditions against a notification |
| Config/options flow | UI for creating and editing receivers |

## 5. User interface

The panel foundation (shell, websocket base, dashboard, receivers list with
enable/disable, pending discoveries) is built; see [docs/ui.md](docs/ui.md)
and [AGENTS.md](AGENTS.md). The remaining views are **TBD**; the intended
scope is:

| View | Purpose |
| --- | --- |
| Recent notifications | History of notifications sent and their delivery |
| Receivers (extend) | Conditions editor (add, edit and remove are built) |
| Notification designer | Compose a notification (targets and content) |
| Dashboard (extend) | Recent activity |
| Testing tool (extend) | Conditions in the preview; rich content |

Notes:

- The panel is admin-only and the websocket commands behind it require an
  admin user. It will expose notification contents and conditions and send
  notifications, so this must stay.
- The designer must build on the `notify.com_system` action, as the
  testing tool does, so it exercises the same code path as automations.
- Warnings about unsupported content are shown in recent notifications;
  the testing tool already shows the warnings an action returns.
- The testing tool (built, see [docs/ui.md](docs/ui.md)) must also show
  receivers skipped because a condition did not pass, once conditions
  exist.
- The receiver editor needs a conditions editor. Home Assistant's condition
  selector can likely be reused.
- The designer must account for receiver-specific content (section 2.3),
  e.g. showing mobile app action options only when relevant.
- Recent notifications requires a history store. History is kept in Home
  Assistant's JSON storage (`Store`), capped by count and age (default to be
  chosen, e.g. last 200 notifications or 30 days, whichever comes first),
  and the limits are configurable in the integration options.
- Websocket commands are still needed for history, resolution preview and
  test sends.
- The pending discoveries list links to Devices & services to add or
  ignore. Doing that inside the panel is not done.
- The release flow (`release.yml`, `zip_release` in `hacs.json`) has not run
  yet; the zip contents were checked locally in the spike only.

## 6. Standards and tooling (proposed, to be confirmed)

- HACS-compatible custom integration (`hacs.json`, `manifest.json`).
- UI config flow; no YAML-only configuration.
- Tests with `pytest-homeassistant-custom-component`.
- CI via GitHub Actions: hassfest, HACS validation, lint, tests.
- Follow Home Assistant developer docs and current core integration quality
  practices.
- Markdown files must pass the default markdownlint rules (including the
  80-character line limit).
- Documentation in `docs/` is maintained alongside the code (section 6.1),
  and `AGENTS.md` records what agents and contributors need to know about
  features as built.
- Integration domain: `com_system`. Display name: "Com System".
- Minimum supported Home Assistant version: the latest stable release at the
  time of building. No compatibility shims for older versions; the minimum
  is raised when needed and recorded in `hacs.json`.

### 6.1 Documentation (`docs/` folder)

The repository maintains a `docs/` folder of user-facing documentation.
`PLAN.md` stays at the repository root as the design and AI context; `docs/`
describes the integration as actually implemented.

- Documentation is updated **as each part is implemented**. A phase or issue
  is not complete until its documentation is written or updated.
- Each topic has its own document. Proposed structure (names provisional):

```text
docs/
  README.md             # index and getting started
  targets.md            # people, areas, explicit receivers, defaults
  content.md            # common and receiver-specific content parameters
  conditions.md         # notification conditions and available variables
  services.md           # notify.com_system and receiver switch actions
  ui.md                 # dashboard, designer, testing tool, history
  receivers/
    README.md           # receiver concept, enabled state, entity
    custom.md           # custom (action-mapped) receivers
    mobile-app.md
    alexa-media-player.md
    persistent-notification.md
    pushover.md
    webostv.md
    music-assistant.md
```

- Each receiver document covers setup, supported content and capabilities,
  and examples. New receiver types add their own document.
- Documents include worked examples, such as a do-not-disturb automation
  using the receiver on/off actions.
- CI lints the markdown but does not enforce that docs change with code.
  The rule is upheld through a pull request template checklist, `CLAUDE.md`
  and review.
- The docs are read in the repository for now, but are written with
  GitHub Pages in mind: relative links between documents, one top-level
  heading per file, no reliance on GitHub-only rendering features, and a
  structure that a static site generator could publish unchanged. No site
  generator is set up initially.
- All documentation follows the markdownlint rule in section 6.

## 7. Delivery

Delivery is tracked as GitHub issues #1 to #29, grouped into milestones M0 to
M7. The issues, not this section, are the source of truth for order and
dependencies. In outline:

- **M0 Foundation** – dev environment with devcontainer and debugging,
  integration skeleton, test harness and CI.
- **M1 Spikes** – the new `notification_receiver` domain, the
  `notify.com_system` action, the hub entry and discovery flows, the mobile
  app person link and the frontend panel build.
- **M2 Core** – receiver model, entities, detection, UI foundation, target
  resolution, the action with a testing tool, mobile app and custom
  receivers (basic notifications: message and title).
- **M3 Receiver types** – persistent notification, Alexa Media Player,
  Pushover and webOS TV.
- **M4 History and rich content** – history, content parameters and the
  designer, mobile app actions and responses.
- **M5 Conditions** – a spike, then notification conditions.
- **M6 Catch-all and release** – rolling UI and documentation tickets, then
  the first release.
- **M7 After first release** – the Music Assistant receiver.

Documentation and UI are delivered with each feature, not as separate
phases. When a feature is complete it is **removed from this plan**: it is
documented in `docs/` and covered in `AGENTS.md`, so this file only describes
work still to do. When the last item is done, this file can be deleted.

## 8. Open questions

- Which Integrations-page titles keep 10 to 30 receiver entries readable?
