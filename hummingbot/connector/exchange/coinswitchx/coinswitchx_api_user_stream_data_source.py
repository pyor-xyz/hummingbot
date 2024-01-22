import asyncio
from typing import List, Optional

from hummingbot.connector.exchange.coinswitchx import coinswitchx_constants as CONSTANTS
from hummingbot.connector.exchange.coinswitchx.coinswitchx_auth import CoinswitchxAuth
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.hummingbot.connector.exchange.coinswitchx.coinswitchx_exchange import CoinswitchxExchange
from hummingbot.hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class CoinswitchxAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CoinswitchxAuth,
                 trading_pairs: List[str],
                 connector: 'CoinswitchxExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: CoinswitchxAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    pass
