from hummingbot.core.api_throttler.data_types import RateLimit

DEFAULT_DOMAIN = "co"

HBOT_ORDER_ID_PREFIX = "55"
MAX_ORDER_ID_LEN = 20

REQUEST_WEIGHT = "REQUEST_WEIGHT"
PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

REST_URL = "sandbox-csx.coinswitch.co"
WSS_URL = "sandbox-websocket.coinswitch.co"

PING_PATH_URL = "v1/public/health/"
GET_BALANCE_PATH_URL = "/v2/me/balance"


ONE_MINUTE = 60

# TICKER_PRICE_CHANGE_PATH_URL = "SubscribeLevel1"
# EXCHANGE_INFO_PATH_URL = "markets"
# SNAPSHOT_PATH_URL = "markets/{}/orderbook"
# SERVER_TIME_PATH_URL = ""

# ACCOUNTS_PATH_URL = "accounts"
# MY_TRADES_PATH_URL = "trades"
# ORDER_PATH_URL = "orders"
# CANCEL_ORDER_PATH_URL = "orders/cancel"
# GET_ORDER_BY_CLIENT_ID = "orders/by-client-order-id/{}"
# GET_ORDER_BY_ID = "orders/by-order-id/{}"


RATE_LIMITS = [RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),]  # TODO
