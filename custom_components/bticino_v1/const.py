"""Constants for the BTicino Door Entry v1 integration."""

# pyright: reportMissingImports=false
from homeassistant.const import Platform

DOMAIN = "bticino_v1"

PLATFORMS = [Platform.LOCK, Platform.LIGHT, Platform.SENSOR]

# API
API_BASE = "https://api.developer.legrand.com"
APIM_SUBSCRIPTION_KEY = "f36968e522bf4ec3877fa491109d3d14"

# Azure B2C auth
B2C_TENANT = "EliotClouduamprd.onmicrosoft.com"
B2C_BASE = "https://eliotclouduamprd.b2clogin.com"
B2C_POLICY = "B2C_1_DoorEliot-C100X-SignUporSignIn"
B2C_CLIENT_ID = "7d11af71-ab98-4832-aa62-6b00bff3bcc8"
B2C_SCOPE = "openid offline_access https://EliotClouduamprd.onmicrosoft.com/security/access.full"
B2C_REDIRECT_URI = "com.legrandgroup.c100x://oauth2redirect"
B2C_USER_AGENT = "NetatmoApp(DoorEntry/v1.8.2) Android(13/Google/sdk_gphone64_arm64)"

# Module device types (from real API response)
DEVICE_TYPE_GATEWAY = "gateway"
DEVICE_TYPE_LOCK = "lock"
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_AV_TERMINAL = "audioVideoTerminal"
MODULE_SUBTYPE_EU = "EU"
MODULE_SUBTYPE_IU = "IU"

# Coordinator
UPDATE_INTERVAL = 5  # minutes

# Lock
LOCK_RELOCK_DELAY = 5  # seconds

# Storage
TOKEN_STORAGE_VERSION = 1

# hass.data keys
COORDINATOR_KEY = "coordinator"
AUTH_KEY = "auth"
API_KEY = "api"

# Default name
DEFAULT_NAME = "BTicino Door Entry v1"
