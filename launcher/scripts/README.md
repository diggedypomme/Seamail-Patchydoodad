# Recommended Script Locations

Put new launcher-managed scripts here when they are no longer just ad-hoc experiments.

Do not move larger imported tool folders in here if they depend on their own templates, static assets,
or internal relative paths. Those belong under `launcher/packages/`.

Suggested layout:

- `translation/`
  - live translation workers
  - menu translation helpers
- `conversion/`
  - model extraction and conversion tools
- `streaming/`
  - XP-side bundle builders
  - UDP bridge helpers
- `admin/`
  - privileged helpers such as hosts-file changes

Existing scripts under `debug_components/` can still be launched directly through the registry until you decide to move them.
