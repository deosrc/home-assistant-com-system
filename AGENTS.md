# Agent and contributor notes

Read [PLAN.md](PLAN.md) for the design of work not yet built.

## Dev environment

- Work in the devcontainer. See the
  [README](README.md#development) for starting Home Assistant, debugging,
  tests and linting.
- The integration lives in `custom_components/com_system/` and is symlinked
  into `config/custom_components/` by `scripts/setup`.
- `config/configuration.yaml` is the only committed file under `config/`.
- Markdown must pass `npm run lint:md` (default rules, 80 columns).
- Update the README, `docs/` and this file when behavior changes.
