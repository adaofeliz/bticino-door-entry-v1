
## DataUpdateCoordinator config_entry parameter (2026-06-05)

HA's newer `DataUpdateCoordinator.__init__` requires `config_entry=entry` to be passed explicitly.
Without it, the base class calls `frame.report_usage()` which requires the HA frame helper ContextVar to be set up — this raises `RuntimeError: Frame helper not set up` in unit tests using plain `MagicMock` for hass.

Fix: always pass `config_entry=entry` as a keyword argument to `super().__init__()`.
