# COM System – Home Assistant Custom Integration Plan

> Status: **Draft v0.1** – planning only, no code yet. This file is the
> source of truth for the design, the basis for the GitHub issues, and the
> context document for AI-assisted implementation. Sections marked **TBD**
> are intentionally unresolved.

## 1. Overview

COM System is a **notification distribution system** for Home Assistant,
built as a custom integration. It uses a **publish/subscribe** model:

- **Notification Receivers** are the subscribers. Each one represents
  something that can receive a notification.
- A notification is **published** by calling the `notify.com_system` action
  provided by this integration.
- COM System decides which receivers the notification applies to (based on
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
2. **Custom receivers** which are mapped to Home Assistant actions
   (services). This is similar to how the existing notifications system maps
   a notifier to a service call.

Each receiver needs (details **TBD**):

- A unique name/ID.
- The mechanism used to deliver to it (an existing service/entity, or a
  user-defined action mapping).
- Association data used for target resolution: which **people** and/or
  **areas** it relates to.

### 2.2 Targets

Targets determine which receivers are triggered by a notification.

- **Specific receivers** – an option to name receivers directly.
- **People** – the main mechanism. Resolves to the receivers associated with
  those people.
- **Areas** – the main mechanism. Resolves to the receivers associated with
  those areas.
- **Default** – when no targets are specified, the notification goes to
  **all people and all areas**.

Only **enabled** receivers (section 2.4) are triggered, whichever way they
were targeted.

Open questions on target resolution are listed in section 8.

### 2.3 Message parameters

The `notify.com_system` action parameters fall into two groups:

1. **Target parameters** – described above.
2. **Content parameters** – describe what the notification says and how it
   behaves once delivered.

Content parameters are split into two tiers:

- **Common content** – supported by (almost) every receiver, e.g. message
  and title. The exact list is **TBD**.
- **Receiver-specific content** – only meaningful for certain receiver
  types, e.g. actions (buttons) on mobile app notifications. The exact list
  and how it is expressed in the action schema are **TBD**.

Receiver-specific content raises a design question: what happens when a
notification carries content that a resolved receiver does not support?
See section 8.

### 2.4 Receiver entity and enabled state

Each Notification Receiver exposes an entity in a new
**`notification_receiver`** domain. A dedicated domain lets entity selectors
and select inputs be filtered to receivers only.

- The entity mimics a **switch**: state is `on` or `off`, where `on` means
  the receiver is currently **enabled** and `off` means disabled.
- The enabled state controls whether the receiver is triggered by
  `notify.com_system`. Disabled receivers are skipped during delivery.
- The state should survive restarts (restored on startup).
- Receivers must be **toggleable from the standard Home Assistant UI**
  (the entity's more-info dialog, and toggle controls on dashboard cards),
  not only through the COM System UI or actions.
- The domain provides actions to change the state:
  `notification_receiver.turn_on`, `notification_receiver.turn_off` and
  (as for switches) `notification_receiver.toggle`.
- Conditions such as do-not-disturb times are **not** built into COM
  System. They are created with ordinary Home Assistant automations that
  call these actions (e.g. turn a receiver off at 22:00 and on at 07:00).
  This keeps the integration simple and avoids duplicating scheduling
  features.

Standard UI requirement:

- The frontend decides which controls to show from the entity's domain, so
  an unrecognised `notification_receiver` domain may only get a generic
  more-info dialog with no toggle. This must be verified early.
- If the standard UI cannot toggle the entity, an alternative will be
  decided at that point. Candidates, to be evaluated then:
  - Expose the enabled state as a real `switch` entity instead (or as well),
    filtered by integration for selectors.
  - Keep the `notification_receiver` entity and add a companion `switch`.
  - Provide the toggle only in the COM System UI plus actions.

Implementation notes:

- Where possible, base the entity on Home Assistant's `ToggleEntity`
  and the `EntityComponent` pattern, so behaviour matches switches.
- Whether a custom integration can cleanly register a brand-new entity
  domain (and its actions) is a risk to validate early. See section 8.

### 2.5 Supported receiver types

Initially supported receiver types, in priority order:

| Priority | Receiver type | Notes (to be verified) |
| --- | --- | --- |
| 1 | Mobile app | Core; per-device notify actions; rich content |
| 2 | Alexa Media Player | Non-native (custom); speech/announcements |
| 3 | Pushover | Core; priority, sound, attachments |
| 4 | webOS TV | Core; on-screen toast notifications |
| 5 | Music Assistant | Announcements via its own actions |

Each type needs a receiver-type definition (names provisional) covering:

- How receivers of that type are discovered and configured.
- Which common and receiver-specific content parameters it supports
  (section 2.3), i.e. its capabilities.
- How a COM System notification is translated into the underlying Home
  Assistant action call.

The custom (user-mapped action) receiver from section 2.1 remains the
fallback for anything not on this list. Further types can be added later,
so the type definition should be an extension point rather than hard-coded.

## 3. The `notify.com_system` action

- Provided by the integration and registered under the `notify` domain.
- Accepts the target parameters (section 2.2) plus the content parameters
  (section 2.3).
- Resolves targets to a set of receivers, drops disabled ones, then delivers
  to each remaining receiver.
- Exact schema, response/return value and error handling: **TBD**.

## 4. Architecture (initial outline)

Proposed layout following Home Assistant custom integration conventions
(domain `com_system`):

```text
custom_components/com_system/
  __init__.py       # setup / unload, registers the notify action
  manifest.json
  config_flow.py    # config + options flow, receiver management
  const.py
  notify.py         # notify.com_system implementation
  notification_receiver.py  # entity domain, entity class, on/off actions
  services.yaml / strings.json / translations/
  websocket_api.py  # commands backing the UI
  frontend/         # panel source and build output (TBD)
  (receiver registry, target resolver, dispatcher modules - TBD)
tests/
```

Core components (names provisional):

| Component | Responsibility |
| --- | --- |
| Receiver registry | Stores and manages configured receivers |
| Target resolver | Maps people, areas or receivers to a set of receivers |
| Receiver entity | `notification_receiver` entity holding enabled state |
| Dispatcher | Delivers to each resolved receiver, handling failures |
| Notify action | Entry point; validates input, calls resolver, dispatcher |
| Config/options flow | UI for creating and editing receivers |

The target resolver also applies the default of "everyone" when no targets
are given.

## 5. User interface

The integration provides its own UI inside Home Assistant (for example a
sidebar panel). Details of each view are **TBD**; the intended scope is:

| View | Purpose |
| --- | --- |
| Dashboard | Overview of the system's state and recent activity |
| Recent notifications | History of notifications sent and their delivery |
| Receivers | View, add, edit and remove configured receivers |
| Notification designer | Compose a notification (targets and content) |
| Testing tool | Send a test notification and see how it resolves |

Notes:

- The designer and testing tool both build on the `notify.com_system`
  action, so they must exercise the same code path as automations.
- The testing tool should show which receivers a notification would reach
  (target resolution) and the per-receiver outcome.
- The designer must account for receiver-specific content (section 2.3),
  e.g. showing mobile app action options only when relevant.
- Recent notifications requires a history store; retention is **TBD**.
- The UI talks to the backend through Home Assistant's websocket API, which
  needs commands for receivers, history, resolution preview and test sends.

## 6. Standards and tooling (proposed, to be confirmed)

- HACS-compatible custom integration (`hacs.json`, `manifest.json`).
- UI config flow; no YAML-only configuration.
- Tests with `pytest-homeassistant-custom-component`.
- CI via GitHub Actions: hassfest, HACS validation, lint, tests.
- Follow Home Assistant developer docs and current core integration quality
  practices.
- Markdown files must pass the default markdownlint rules (including the
  80-character line limit).

## 7. Proposed delivery phases (draft, to become GitHub issues)

1. **Scaffold** – repository structure, manifest, HACS metadata, CI, test
   harness, `CLAUDE.md` pointing to this plan.
2. **Receiver model and storage** – data model, registry, persistence.
3. **Receiver entities** – `notification_receiver` domain, switch-like
   entity with restored state, `turn_on`/`turn_off`/`toggle` actions. Starts
   with a spike to validate registering a new domain and that the standard
   Home Assistant UI can toggle it; decide the alternative if not.
4. **Receiver config flow** – create/edit/remove receivers via the UI
   (built-in and custom action-mapped).
5. **Target resolution** – people, areas, explicit receivers,
   default-to-all behaviour.
6. **`notify.com_system` action** – schema, wiring to resolver and
   dispatcher, delivery and error handling.
7. **Content parameters** – common content first, then receiver-specific
   content (e.g. mobile app actions) with per-receiver-type handling.
8. **Receiver types** – extensible type definition, then in priority order:
   mobile app, Alexa Media Player, Pushover, webOS TV, Music Assistant.
9. **History store** – persist recent notifications and delivery results.
10. **Websocket API** – commands for receivers, history, preview and test.
11. **UI** – panel shell and dashboard, then recent notifications,
   receivers, notification designer and testing tool.
12. **Documentation and release** – README, examples, HACS release.

## 8. Open questions

- Which content parameters are common, and which are receiver-specific?
- How are receiver-specific parameters expressed in the action schema: a
  free-form `data` block, per-receiver-type blocks, or typed fields?
- When a receiver does not support a piece of content, is it ignored,
  downgraded (e.g. actions folded into the message text) or treated as an
  error?
- How does a receiver declare its type and capabilities, and can custom
  receivers declare their own?
- How are responses to notification actions (e.g. a button press on a mobile
  notification) surfaced, given one notification may reach many receivers?
- How is a receiver associated with a person or area? Explicit mapping on
  the receiver, or derived from the entity, device or area registry?
- When both people and areas are given, is the result a union or an
  intersection?
- Can a custom integration register a new `notification_receiver` entity
  domain (with its own actions) cleanly? Should it live in `com_system` or a
  separate integration? Fallback: `switch` entities filtered by integration.
- Does the standard Home Assistant UI (more-info dialog, tile and entity
  cards) offer a toggle for a `notification_receiver` entity? If not, which
  alternative is chosen (see section 2.4)?
- How are receivers stored: config entries, config subentries or stored
  data, with entities derived from them?
- If a disabled receiver is named explicitly as a target, is it still
  skipped? Does the testing tool show disabled receivers as skipped?
- Should the entity expose attributes (type, associated people and areas,
  last triggered)?
- How are delivery failures reported (per receiver, aggregated, or
  fire-and-forget)?
- Frontend approach: custom panel built with Lit/web components, or other?
  Build and release process for the frontend assets.
- How much history is kept, where is it stored (HA storage or database),
  and is it configurable?
- Should the UI be admin-only, or visible to all users?
- How does each supported type deliver notifications: which actions or
  entities does it use, and how are its receivers discovered?
- Alexa Media Player is a non-native integration: how do we handle it being
  absent, and its differing action names across versions?
- Music Assistant announcements are not a notify action: how does the
  receiver model accommodate non-notify delivery mechanisms?
- Should receivers of a type be created automatically from the underlying
  integration's actions/entities, or added manually?
- Minimum supported Home Assistant version.
- Domain name and display name confirmation (`com_system` assumed).
