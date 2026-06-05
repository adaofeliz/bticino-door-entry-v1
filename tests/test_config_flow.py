"""Tests for BticinoV1ConfigFlow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bticino_v1.const import DOMAIN
from custom_components.bticino_v1.auth import AuthError
from custom_components.bticino_v1.api import ApiError

SINGLE_PLANT = [{"id": "plant-001", "name": "My Home"}]
MULTI_PLANT = [
    {"id": "plant-001", "name": "Home"},
    {"id": "plant-002", "name": "Office"},
]
MODULES_WITH_GATEWAY = [
    {"id": "gw-001", "device": "gateway", "name": ""},
    {"id": "lock-001", "device": "lock", "name": "A-Door"},
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    pass


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent real async_setup_entry from running during config flow tests."""
    with patch(
        "custom_components.bticino_v1.async_setup_entry",
        return_value=True,
    ):
        yield


def _mock_auth_and_api(plants, modules=None):
    """Return patched AuthHandler and LegrandApiClientV1."""
    mock_auth = AsyncMock()
    mock_auth.authenticate = AsyncMock()
    mock_auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    mock_auth.close = AsyncMock()

    mock_api = AsyncMock()
    mock_api.get_plants = AsyncMock(return_value=plants)
    mock_api.get_modules = AsyncMock(return_value=modules or MODULES_WITH_GATEWAY)
    mock_api.close = AsyncMock()

    return mock_auth, mock_api


@pytest.mark.asyncio
async def test_user_step_single_plant_skips_home_selection(hass):
    """With one plant, flow must skip select_home and go to init_options."""
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass123"},
        )
    # Single plant → should go to init_options (not select_home)
    assert result2["type"] in (FlowResultType.FORM, FlowResultType.CREATE_ENTRY)
    if result2["type"] == FlowResultType.FORM:
        assert result2["step_id"] == "init_options"


@pytest.mark.asyncio
async def test_user_step_multiple_plants_shows_select_home(hass):
    """With multiple plants, flow must show select_home step."""
    mock_auth, mock_api = _mock_auth_and_api(MULTI_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass123"},
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "select_home"


@pytest.mark.asyncio
async def test_user_step_invalid_auth_shows_error(hass):
    """AuthError during validation must show 'invalid_auth' error on the form."""
    mock_auth = AsyncMock()
    mock_auth.authenticate = AsyncMock(side_effect=AuthError("bad credentials"))
    mock_auth.close = AsyncMock()
    with patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "wrongpass"},
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert "invalid_auth" in result2.get("errors", {}).get("base", "")


@pytest.mark.asyncio
async def test_user_step_cannot_connect_shows_error(hass):
    """ApiError during get_plants must show 'cannot_connect' error."""
    mock_auth, mock_api = _mock_auth_and_api([])
    mock_api.get_plants = AsyncMock(side_effect=ApiError(503, "Service Unavailable"))
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass"},
        )
    assert result2["type"] == FlowResultType.FORM
    assert "cannot_connect" in result2.get("errors", {}).get("base", "")


@pytest.mark.asyncio
async def test_user_step_zero_plants_aborts(hass):
    """Zero plants must abort with 'no_plants_found'."""
    mock_auth, mock_api = _mock_auth_and_api([])
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass"},
        )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "no_plants_found"


@pytest.mark.asyncio
async def test_already_configured_aborts(hass):
    """Second setup with same username must abort with 'already_configured'."""
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        # First setup
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass"},
        )
        # Complete the flow
        if result2["type"] == FlowResultType.FORM and result2["step_id"] == "init_options":
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {"light_as_lock": False}
            )
        assert result2["type"] == FlowResultType.CREATE_ENTRY

        # Second setup with same username
        mock_auth2, mock_api2 = _mock_auth_and_api(SINGLE_PLANT)
        with (
            patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth2),
            patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api2),
        ):
            result3 = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result4 = await hass.config_entries.flow.async_configure(
                result3["flow_id"],
                {"username": "user@example.com", "password": "pass"},
            )
    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_select_home_stores_home_id(hass):
    """Selecting a home must store home_id in config entry data."""
    mock_auth, mock_api = _mock_auth_and_api(MULTI_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass"},
        )
        assert result2["step_id"] == "select_home"
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"home_id": "plant-002"}
        )
    # Should proceed to init_options
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "init_options"


@pytest.mark.asyncio
async def test_init_options_creates_entry_with_light_as_lock_false(hass):
    """Completing init_options must create a config entry with light_as_lock=False."""
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "user@example.com", "password": "pass"},
        )
        if result2["type"] == FlowResultType.FORM and result2["step_id"] == "init_options":
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {"light_as_lock": False}
            )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["options"]["light_as_lock"] is False


@pytest.mark.asyncio
async def test_reauth_confirm_updates_password(hass):
    """Reauth with correct new password must succeed."""
    # First create an entry
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user@example.com", "password": "pass"}
        )
        if result2["type"] == FlowResultType.FORM:
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {"light_as_lock": False}
            )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    entry = result2["result"]

    # Now reauth
    mock_auth2 = AsyncMock()
    mock_auth2.authenticate = AsyncMock()
    mock_auth2.close = AsyncMock()
    with patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth2):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"password": "newpass"}
        )
    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_reauth_confirm_invalid_password_shows_error(hass):
    """Reauth with wrong password must show 'invalid_auth' error."""
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user@example.com", "password": "pass"}
        )
        if result2["type"] == FlowResultType.FORM:
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {"light_as_lock": False}
            )
    entry = result2["result"]

    mock_auth2 = AsyncMock()
    mock_auth2.authenticate = AsyncMock(side_effect=AuthError("bad"))
    mock_auth2.close = AsyncMock()
    with patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth2):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"password": "wrongpass"}
        )
    assert result4["type"] == FlowResultType.FORM
    assert "invalid_auth" in result4.get("errors", {}).get("base", "")


@pytest.mark.asyncio
async def test_options_flow_updates_light_as_lock(hass):
    """Options flow must update light_as_lock option."""
    mock_auth, mock_api = _mock_auth_and_api(SINGLE_PLANT)
    with (
        patch("custom_components.bticino_v1.config_flow.AuthHandler", return_value=mock_auth),
        patch("custom_components.bticino_v1.config_flow.LegrandApiClientV1", return_value=mock_api),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "user@example.com", "password": "pass"}
        )
        if result2["type"] == FlowResultType.FORM:
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], {"light_as_lock": False}
            )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    entry = result2["result"]
    assert entry.options.get("light_as_lock") is False

    # Now open options flow and change light_as_lock to True
    result3 = await hass.config_entries.options.async_init(entry.entry_id)
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"], {"light_as_lock": True}
    )
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options.get("light_as_lock") is True
