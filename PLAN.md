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

## 3. The `notify.com_system` action

- Provided by the integration and registered under the `notify` domain.
- Accepts the target parameters (section 2.2) plus the content parameters
  (section 2.3).
- Resolves targets to a set of receivers, then delivers to each receiver.
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
3. **Receiver config flow** – create/edit/remove receivers via the UI
   (built-in and custom action-mapped).
4. **Target resolution** – people, areas, explicit receivers,
   default-to-all behaviour.
5. **`notify.com_system` action** – schema, wiring to resolver and
   dispatcher, delivery and error handling.
6. **Content parameters** – common content first, then receiver-specific
   content (e.g. mobile app actions) with per-receiver-type handling.
7. **History store** – persist recent notifications and delivery results.
8. **Websocket API** – commands for receivers, history, preview and test.
9. **UI** – panel shell and dashboard, then recent notifications,
   receivers, notification designer and testing tool.
10. **Documentation and release** – README, examples, HACS release.

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
- Are receivers HA entities, config entries, config subentries or stored
  data only?
- How are delivery failures reported (per receiver, aggregated, or
  fire-and-forget)?
- Frontend approach: custom panel built with Lit/web components, or other?
  Build and release process for the frontend assets.
- How much history is kept, where is it stored (HA storage or database),
  and is it configurable?
- Should the UI be admin-only, or visible to all users?
- Minimum supported Home Assistant version.
- Domain name and display name confirmation (`com_system` assumed).
