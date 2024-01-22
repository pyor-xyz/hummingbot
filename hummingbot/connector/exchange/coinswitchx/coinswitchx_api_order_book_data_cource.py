import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.coinswitchx import (
    coinswitchx_constants as CONSTANTS,
    coinswitchx_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinswitchx.coinswitchx_order_book import CoinswitchxOrderBook
from hummingbot.connector.exchange.coinswitchx.socket_assistant.socketio_assistant import SocketIoAssistant
from hummingbot.connector.exchange.coinswitchx.socket_assistant.socketio_assistants_factory import (
    SocketIoAssistantsFactory,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinswitchx.coinswitchx_exchange import CoinswitchxExchange


class CoinswitchxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CoinswitchxExchange',
                 api_factory: SocketIoAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "instrument": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_params = []
            depth_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_params.append(symbol)
                depth_params.append(symbol)
            payload = {
                "event": "subscribe",
                "pair": trade_params,
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "event": "subscribe",
                "pair": depth_params,
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> SocketIoAssistant:
        si: SocketIoAssistant = await self._api_factory.get_socketio_assistant
        await si.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return si

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CoinswitchxOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
            trade_message = CoinswitchxOrderBook.trade_message_from_exchange(
                raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
            order_book_message: OrderBookMessage = CoinswitchxOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("e")
            channel = (self._diff_messages_queue_key if event_type == CONSTANTS.DIFF_EVENT_TYPE
                       else self._trade_messages_queue_key)
        return channel
