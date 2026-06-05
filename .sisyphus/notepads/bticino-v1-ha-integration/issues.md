# Issues
- Host environment did not have `homeassistant` installed, so the verification `python -c "from homeassistant.const import Platform"` failed until I created a temporary venv and installed the dependency there.

- Pyright diagnostics flag missing `homeassistant` imports for tests/test_entity.py and entity.py because the dependency graph is not available in this workspace; YAML stubs would be needed to silence these warnings, but runtime verification already succeeds.
- `lsp_diagnostics` now reports the same missing-homeassistant/imports noise (and derived unknown-member warnings) for `custom_components/bticino_v1/lock.py` and `tests/test_lock.py`. These cannot be fixed without real HA stubs or packages, so the errors are expected and the tests still pass.
- Pyright diagnostics still complain about missing `homeassistant` imports and related type noise for `custom_components/bticino_v1/light.py` and `tests/test_light.py`; I suppressed the missing-import errors with `# pyright: reportMissingImports=false`, leaving only warnings.
- Sensor tests also depend on HA imports that are not present in the default workspace, so the check must run inside `/tmp/ha_verify_venv` or another env where `homeassistant` is installed.
