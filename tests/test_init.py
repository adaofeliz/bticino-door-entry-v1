"""Tests for bticino_v1 __init__.py entry lifecycle."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.bticino_v1.const import DOMAIN, COORDINATOR_KEY, AUTH_KEY, API_KEY
from custom_components.bticino_v1.auth import AuthError
from custom_components.bticino_v1.api import ApiError


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    pass


@pytest.fixture
def mock_config_entry(hass):
    """Create a mock config entry registered with HA."""
    from homeassistant.config_entries import ConfigEntry
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id_001"
    entry.domain = DOMAIN
    entry.data = {
        "username": "fixture@example.com",
        "password": "fixture_password",
        "home_id": "plant-id-001",
        "gateway_id": "gateway-id-001",
    }
    entry.options = {"light_as_lock": False}
    entry.state = ConfigEntryState.NOT_LOADED
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=lambda: None)
    return entry


def _make_mock_coordinator():
    coordinator = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.data = {
        "modules": {"gateway-id-001": {"id": "gateway-id-001", "device": "gateway"}},
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    coordinator.gateway_id = "gateway-id-001"
    coordinator.last_update_success = True
    return coordinator


@pytest.mark.asyncio
async def test_setup_entry_stores_coordinator_in_hass_data(hass, mock_config_entry):
    """async_setup_entry must store coordinator in hass.data[DOMAIN][entry_id]."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()
    mock_coordinator = _make_mock_coordinator()

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.LegrandApiClientV1"),
        patch("custom_components.bticino_v1.BticinoV1Coordinator", return_value=mock_coordinator),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert COORDINATOR_KEY in hass.data[DOMAIN][mock_config_entry.entry_id]


@pytest.mark.asyncio
async def test_setup_entry_auth_error_raises_config_entry_auth_failed(hass, mock_config_entry):
    """AuthError during token validation must raise ConfigEntryAuthFailed."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(side_effect=AuthError("expired"))
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_setup_entry_api_error_raises_config_entry_not_ready(hass, mock_config_entry):
    """First coordinator refresh failure must raise ConfigEntryNotReady."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()
    mock_coordinator = AsyncMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=ConfigEntryNotReady("API down")
    )

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.LegrandApiClientV1"),
        patch("custom_components.bticino_v1.BticinoV1Coordinator", return_value=mock_coordinator),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_setup_entry_restores_tokens_from_store(hass, mock_config_entry):
    """Saved tokens must be restored via auth.set_tokens() on startup."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()
    mock_coordinator = _make_mock_coordinator()

    saved_tokens = {
        "access_token": "eyJSAVED",
        "refresh_token": "SAVED_REFRESH",
        "expires_at": 9999999999.0,
    }

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.LegrandApiClientV1"),
        patch("custom_components.bticino_v1.BticinoV1Coordinator", return_value=mock_coordinator),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=saved_tokens)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry
        await async_setup_entry(hass, mock_config_entry)

    mock_auth.set_tokens.assert_called_once_with(
        access_token="eyJSAVED",
        refresh_token="SAVED_REFRESH",
        expires_at=9999999999.0,
    )


@pytest.mark.asyncio
async def test_unload_entry_cleans_hass_data(hass, mock_config_entry):
    """async_unload_entry must remove entry from hass.data[DOMAIN]."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()
    mock_coordinator = _make_mock_coordinator()

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.LegrandApiClientV1"),
        patch("custom_components.bticino_v1.BticinoV1Coordinator", return_value=mock_coordinator),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
        patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)),
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry, async_unload_entry
        await async_setup_entry(hass, mock_config_entry)
        assert mock_config_entry.entry_id in hass.data.get(DOMAIN, {})

        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_unload_entry_closes_auth_session(hass, mock_config_entry):
    """async_unload_entry must call auth.close()."""
    mock_auth = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.set_tokens = MagicMock()
    mock_auth.close = AsyncMock()
    mock_coordinator = _make_mock_coordinator()

    with (
        patch("custom_components.bticino_v1.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.LegrandApiClientV1"),
        patch("custom_components.bticino_v1.BticinoV1Coordinator", return_value=mock_coordinator),
        patch("custom_components.bticino_v1.Store") as mock_store_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
        patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)),
    ):
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_setup_entry, async_unload_entry
        await async_setup_entry(hass, mock_config_entry)
        await async_unload_entry(hass, mock_config_entry)

    mock_auth.close.assert_called_once()


@pytest.mark.asyncio
async def test_remove_entry_deletes_store(hass, mock_config_entry):
    """async_remove_entry must call store.async_remove()."""
    with patch("custom_components.bticino_v1.Store") as mock_store_cls:
        mock_store = AsyncMock()
        mock_store.async_remove = AsyncMock()
        mock_store_cls.return_value = mock_store

        from custom_components.bticino_v1 import async_remove_entry
        await async_remove_entry(hass, mock_config_entry)

    mock_store.async_remove.assert_called_once()
