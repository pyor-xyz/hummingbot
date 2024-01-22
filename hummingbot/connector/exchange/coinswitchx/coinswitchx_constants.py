from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "co"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

HBOT_ORDER_ID_PREFIX = "55"
MAX_ORDER_ID_LEN = 20

REST_URL = "sandbox-csx.coinswitch.co"  # TODO
WSS_URL = "sandbox-websocket.coinswitch.co"

PING_PATH_URL = "v1/public/health/"
GET_BALANCE_PATH_URL = "v2/me/balance/"
EXCHANGE_INFO_PATH_URL = "v1/public/instrument/"
ORDER_PATH_URL = "v1/orders/"
CANCEL_ORDER_PATH_URL = "v1/orders/{}"
GET_ORDER_BY_ID = "v1/orders/{}"
SNAPSHOT_PATH_URL = "v2/public/depth/"

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 100

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# TODO fix rate limits
RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=100, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    # Weighted Limits
    # RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[(LinkedLimitWeightPair(REQUEST_WEIGHT, 10))]),
    # RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=GET_BALANCE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=GET_ORDER_BY_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    # RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(ORDERS, 1),
    #                          LinkedLimitWeightPair(ORDERS_24HR, 1)]),
]

# Websocket event types
DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"

WS_HEARTBEAT_TIME_INTERVAL = 30
