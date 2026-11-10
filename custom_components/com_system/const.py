"""Constants for the Com System integration."""

DOMAIN = "com_system"

# Config entry data key and values that tell the hub and receivers apart.
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_HUB = "hub"
ENTRY_TYPE_CUSTOM_RECEIVER = "custom_receiver"
# A receiver of a built-in type, created from a discovery.
ENTRY_TYPE_RECEIVER = "receiver"

# Entry types that are receivers. Each receiver type maps to one of these.
RECEIVER_ENTRY_TYPES = (ENTRY_TYPE_CUSTOM_RECEIVER, ENTRY_TYPE_RECEIVER)

CONF_NAME = "name"

# Receiver entry data: the receiver type id and, for receivers attached to
# another integration's device, the identifier of that source device.
CONF_RECEIVER_TYPE = "receiver_type"
CONF_SOURCE_ID = "source_id"
RECEIVER_TYPE_CUSTOM = "custom"

# Receiver entry options: who and where the receiver relates to.
CONF_PEOPLE = "people"
CONF_AREAS = "areas"

# The domain of the read-only receiver entity, which com_system provides.
NOTIFICATION_RECEIVER_DOMAIN = "notification_receiver"

# Keys of ``hass.data[DOMAIN]``.
DATA_REGISTRY = "registry"
DATA_COMPONENT = "notification_receiver_component"
DATA_ENTITIES = "entities"

# Delivery results, used as the event types of the receiver entity.
RESULT_DELIVERED = "delivered"
RESULT_FAILED = "failed"
RESULT_SKIPPED = "skipped"
RESULTS = (RESULT_DELIVERED, RESULT_FAILED, RESULT_SKIPPED)

# Receiver type ids of the built-in types.
RECEIVER_TYPE_MOBILE_APP = "mobile_app"
RECEIVER_TYPE_ALEXA_MEDIA = "alexa_media"
RECEIVER_TYPE_PERSISTENT_NOTIFICATION = "persistent_notification"
RECEIVER_TYPE_PUSHOVER = "pushover"
RECEIVER_TYPE_WEBOSTV = "webostv"
RECEIVER_TYPE_MUSIC_ASSISTANT = "music_assistant"

# Keys of the discovery payload the hub passes to the discovery flow.
CONF_DISCOVERY_TYPE = "receiver_type"

# How often the hub detects again, and how long it waits after a device
# registry change so a burst of changes causes one detection.
DETECTION_INTERVAL_SECONDS = 3600
DETECTION_DEBOUNCE_SECONDS = 5
