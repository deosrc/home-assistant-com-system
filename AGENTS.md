# Agent and contributor notes

Read [PLAN.md](PLAN.md) for the design of work not yet built. This file
records the conventions and how things work as built.

## Rules

- Ship documentation (`docs/`, and the README where relevant) and UI with
  each feature, not as a later step.
- Update this file when behavior or architecture changes.
- When a feature is complete, remove it from `PLAN.md`.
- Markdown must pass `npm run lint:md` (default rules, 80 columns).

## Dev environment

- Work in the devcontainer. See the
  [README](README.md#development) for starting Home Assistant, debugging,
  tests and linting.
- The integration lives in `custom_components/com_system/` and is symlinked
  into `config/custom_components/` by `scripts/setup`.
- `config/configuration.yaml` is the only committed file under `config/`.

## Commands

- Start Home Assistant: `scripts/develop` (or the **Start Home Assistant**
  task). Debug with the **Home Assistant: attach** launch config.
- Test: `python3 -m pytest tests`. Tests use
  `pytest-homeassistant-custom-component`; `tests/conftest.py` enables
  custom integrations for every test.
- Lint Python: `ruff check .` and `ruff format --check .` (format with
  `ruff format .`). Ruff is configured in `pyproject.toml`.
- Lint Markdown: `npm run lint:md`.

## Architecture as built

- Domain `com_system`. The manifest does not use `single_config_entry`
  because receivers are separate config entries.
- One hub entry (`entry_type: hub`) and one entry per receiver
  (`entry_type: custom_receiver` so far, listed in `RECEIVER_ENTRY_TYPES`);
  see `const.py`.
- Receiver entry data: `entry_type`, `receiver_type` (missing means
  `custom`), `name`, optional `source_id`. Options: `people` (`person.*`
  entity ids) and `areas` (area ids). Entries are the only storage.
- `receiver.py`: frozen `Receiver` dataclass built by `Receiver.from_entry`.
- `receiver_type.py`: `ReceiverType` is the extension point (id, name,
  capabilities, `async_deliver`, association hooks, `async_detect`).
  Subclass it and call `register_receiver_type()` to add a type; ids are
  unique. `CustomReceiverType` is the generic type. `async_deliver` and
  discovery are not wired up yet.
- `registry.py`: `ReceiverRegistry` reads receivers from the config entries
  on each call, so it is always current and needs no hub or load order. It
  is created once in `async_setup` as `hass.data[DOMAIN]["registry"]`.
  Unknown types stay listed (`type_of` returns `None`).
- `config_flow.py`: the user step creates the hub if none exists, otherwise
  it continues to `custom_receiver` (name only). One hub is enforced there.
  The options flow of a receiver edits its people and areas; the hub's
  options flow is a stub. Integration discovery and reconfigure are stubs.
- `__init__.py`: `async_setup` creates the registry; entry setup and unload
  are no-ops.
- Strings live in `strings.json`; `translations/en.json` is a copy and must
  be kept in step.
- `hacs.json` records the minimum Home Assistant version; keep it in step
  with `requirements-dev.txt`.

## CI

GitHub Actions workflows in `.github/workflows/` run on pull requests and
pushes to `main`: `lint.yml` (Ruff check and format), `tests.yml` (pytest on
Python 3.14), `markdownlint.yml`, `hassfest.yml` and `hacs.yml` (HACS
validation). Hassfest also runs nightly. All must pass.

HACS validation is temporarily manual-only (`workflow_dispatch`) because the
HACS action fails on a private repository. Restore its triggers when the
repository is made public.
