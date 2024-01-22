from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinswitchx import (
    coinswitchx_constants as CONSTANTS,
    coinswitchx_utils,
    coinswitchx_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinswitchx.coinswitchx_api_order_book_data_cource import (
    CoinswitchxAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.coinswitchx.coinswitchx_api_user_stream_data_source import (
    CoinswitchxAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.coinswitchx.coinswitchx_auth import CoinswitchxAuth
from hummingbot.connector.exchange.coinswitchx.socket_assistant.socketio_assistants_factory import (
    SocketIoAssistantsFactory,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinswitchxExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 coinswitchx_api_key: str,
                 coinswitchx_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN
                 ):
        self.api_key = coinswitchx_api_key
        self.secret_key = coinswitchx_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._socketio_assistant_factory: SocketIoAssistantsFactory = self._create_socketio_assistants_factory()
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return "coinswitchx"

    @property
    def authenticator(self):
        return CoinswitchxAuth(
            api_key = self.api_key,
            secret_key = self.secret_key,
            time_provider=self._time_synchronizer
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True  # TODO

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT]

    def coinswitchx_order_type(order_type: OrderType) -> str:
        if order_type == OrderType.LIMIT or order_type == OrderType.MARKET:
            return order_type.name.lower()
        else:
            raise Exception("Order type not supported by Coinswitchx.")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        pass

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "data": {
                "instruments": [
                    {
                        "instrument": "1INCH/INR",
                        "basePrecision": "0.1",
                        "quotePrecision": "0.01",
                        "limitPrecision": "0.01"
                    },
                    {
                        "instrument": "AAVE/INR",
                        "basePrecision": "0.001",
                        "quotePrecision": "0.01",
                        "limitPrecision": "1"
                    }
                ]
            }
        }
        """
        trading_pair_rules = exchange_info_dict.get("data", {}).get("instruments", [])
        retval = []
        for rule in filter(coinswitchx_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("instrument"))
                # TODO
                # filters = rule.get("filters")
                # price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                # lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                # min_notional_filter = [f for f in filters if f.get("filterType") in ["MIN_NOTIONAL", "NOTIONAL"]][0]

                # min_order_size = Decimal(lot_size_filter.get("minQty"))
                # tick_size = price_filter.get("tickSize")
                # step_size = Decimal(lot_size_filter.get("stepSize"))
                # min_notional = Decimal(min_notional_filter.get("minNotional"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=0.1,
                                min_price_increment=Decimal(0.1),
                                min_base_amount_increment=Decimal(0.1),
                                min_notional_size=Decimal(0.1)))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trade_base_fee = build_trade_fee(
            exchange=self.name,
            is_maker=is_maker,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price,
            base_currency=base_currency,
            quote_currency=quote_currency
        )
        return trade_base_fee

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(coinswitchx_utils.is_exchange_information_valid, exchange_info.get("data", {}).get("instruments", [])):
            asset_pair = symbol_data["instrument"].split('/')
            mapping[symbol_data["instrument"]] = combine_to_hb_trading_pair(base=asset_pair[0],
                                                                            quote=asset_pair[1])
        self._set_trading_pair_symbol_map(mapping)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        try:
            cancel_result = await self._api_delete(
                path_url=CONSTANTS.CANCEL_ORDER_PATH_URL.format(order_id),
                is_auth_required=True)
        except OSError as e:
            if "HTTP status is 404" in str(e):
                return True
            raise e

        if len(cancel_result.get("data")) > 0:
            if cancel_result.get("data").get('cancelled') == "true":
                return True

        return False

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           ) -> Tuple[str, float]:
        order_result = None
        amount_str = str(amount)
        price_str = str(price)
        type_str = CoinswitchxExchange.coinswitchx_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        req_body = {
            "instrument": symbol,
            "side": side_str,
            "quantity": amount_str,
            "type": type_str,
            "clientOrderId": order_id,
            "username": "",  # TODO
        }
        if order_type == OrderType.LIMIT:
            req_body["limitPrice"] = price_str

        self.logger().info(f'New order sent with these fields: {req_body}')

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=req_body,
            is_auth_required=True
        )
        exchange_order_id = str(order_result['data']["orderId"])
        transact_time = int(datetime.now(timezone.utc).timestamp() * 1e3)
        return exchange_order_id, transact_time

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_BY_ID.format(tracked_order.exchange_order_id),
            is_auth_required=True,
        )

        new_state = CONSTANTS.ORDER_STATE[updated_order_data['data']["status"]]

        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=(datetime.now(timezone.utc).timestamp() * 1e3),
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data.get("id")),
        )

        return order_update

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    def _create_socketio_assistants_factory(self) -> SocketIoAssistantsFactory:
        return web_utils.build_socketio_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinswitchxAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._socketio_assistant_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinswitchxAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._socketio_assistant_factory,
            domain=self.domain,
        )

    async def _user_stream_event_listener(self):
        pass

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        data = await self._api_get(
            path_url = CONSTANTS.GET_BALANCE_PATH_URL,
            is_auth_required = True
        )

        balances = data.get("data")
        available = balances.get("Available")
        if "Available" in balances and available is None:
            available = {}
        locked = balances.get("Locked")
        if "Locked" in balances and locked is None:
            locked = {}
        assets = set(available.keys()) | set(locked.keys())

        for asset in assets:
            asset_name = asset.upper()
            free_balance_raw = available.get(asset, '0')
            free_balance = coinswitchx_utils.decimal_val_or_none(string_value = free_balance_raw)
            locked_balance_raw = locked.get(asset, '0')
            locked_balance = coinswitchx_utils.decimal_val_or_none(string_value = locked_balance_raw)
            total_balance = free_balance + locked_balance
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
