import asyncio
from typing import Any, Dict, List, Mapping, Optional, Tuple

from bidict import bidict
from google.protobuf import any_pb2
from pyinjective import Transaction
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer, injective_exchange_tx_pb
from pyinjective.core.network import Network

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source import InjectiveDataSource
from hummingbot.connector.exchange.injective_v2.injective_market import (
    InjectiveDerivativeMarket,
    InjectiveSpotMarket,
    InjectiveToken,
)
from hummingbot.connector.exchange.injective_v2.injective_query_executor import PythonSDKInjectiveQueryExecutor
from hummingbot.connector.gateway.common_types import PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder, GatewayPerpetualInFlightOrder
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderUpdate
from hummingbot.core.pubsub import PubSub
from hummingbot.logger import HummingbotLogger


class InjectiveReadOnlyDataSource(InjectiveDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            network: Network,
            rate_limits: List[RateLimit],
            use_secure_connection: bool = True):
        self._network = network
        self._client = AsyncClient(
            network=self._network,
            insecure=not use_secure_connection,
        )
        self._composer = None
        self._query_executor = PythonSDKInjectiveQueryExecutor(sdk_client=self._client)

        self._publisher = PubSub()
        self._last_received_message_time = 0
        self._throttler = AsyncThrottler(rate_limits=rate_limits)

        self._markets_initialization_lock = asyncio.Lock()
        self._spot_market_info_map: Optional[Dict[str, InjectiveSpotMarket]] = None
        self._derivative_market_info_map: Optional[Dict[str, InjectiveDerivativeMarket]] = None
        self._spot_market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._derivative_market_and_trading_pair_map: Optional[Mapping[str, str]] = None
        self._tokens_map: Optional[Dict[str, InjectiveToken]] = None
        self._token_symbol_symbol_and_denom_map: Optional[Mapping[str, str]] = None

        self._events_listening_tasks: List[asyncio.Task] = []

    @property
    def publisher(self):
        return self._publisher

    @property
    def query_executor(self):
        return self._query_executor

    @property
    def order_creation_lock(self) -> asyncio.Lock:
        return None

    @property
    def throttler(self):
        return self._throttler

    @property
    def portfolio_account_injective_address(self) -> str:
        raise NotImplementedError

    @property
    def portfolio_account_subaccount_id(self) -> str:
        raise NotImplementedError

    @property
    def trading_account_injective_address(self) -> str:
        raise NotImplementedError

    @property
    def injective_chain_id(self) -> str:
        return self._network.chain_id

    @property
    def fee_denom(self) -> str:
        return self._network.fee_denom

    @property
    def portfolio_account_subaccount_index(self) -> int:
        raise NotImplementedError

    @property
    def network_name(self) -> str:
        return self._network.string()

    async def composer(self) -> Composer:
        if self._composer is None:
            self._composer = await self._client.composer()
        return self._composer

    async def timeout_height(self) -> int:
        raise NotImplementedError

    async def spot_market_and_trading_pair_map(self):
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()
        return self._spot_market_and_trading_pair_map.copy()

    async def spot_market_info_for_id(self, market_id: str):
        if self._spot_market_info_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_info_map is None:
                    await self.update_markets()

        return self._spot_market_info_map[market_id]

    async def derivative_market_and_trading_pair_map(self):
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()
        return self._derivative_market_and_trading_pair_map.copy()

    async def derivative_market_info_for_id(self, market_id: str):
        if self._derivative_market_info_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_info_map is None:
                    await self.update_markets()

        return self._derivative_market_info_map[market_id]

    async def trading_pair_for_market(self, market_id: str):
        if self._spot_market_and_trading_pair_map is None or self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None or self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        trading_pair = self._spot_market_and_trading_pair_map.get(market_id)

        if trading_pair is None:
            trading_pair = self._derivative_market_and_trading_pair_map[market_id]
        return trading_pair

    async def market_id_for_spot_trading_pair(self, trading_pair: str) -> str:
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._spot_market_and_trading_pair_map.inverse[trading_pair]

    async def market_id_for_derivative_trading_pair(self, trading_pair: str) -> str:
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        return self._derivative_market_and_trading_pair_map.inverse[trading_pair]

    async def spot_markets(self):
        if self._spot_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._spot_market_and_trading_pair_map is None:
                    await self.update_markets()

        return list(self._spot_market_info_map.values())

    async def derivative_markets(self):
        if self._derivative_market_and_trading_pair_map is None:
            async with self._markets_initialization_lock:
                if self._derivative_market_and_trading_pair_map is None:
                    await self.update_markets()

        return list(self._derivative_market_info_map.values())

    async def token(self, denom: str) -> InjectiveToken:
        if self._tokens_map is None:
            async with self._markets_initialization_lock:
                if self._tokens_map is None:
                    await self.update_markets()

        return self._tokens_map.get(denom)

    def events_listening_tasks(self) -> List[asyncio.Task]:
        return self._events_listening_tasks.copy()

    def add_listening_task(self, task: asyncio.Task):
        self._events_listening_tasks.append(task)

    def configure_throttler(self, throttler: AsyncThrottlerBase):
        self._throttler = throttler

    async def trading_account_sequence(self) -> int:
        raise NotImplementedError

    async def trading_account_number(self) -> int:
        raise NotImplementedError

    async def initialize_trading_account(self):  # pragma: no cover
        # Do nothing
        pass

    async def update_markets(self):
        self._tokens_map = {}
        self._token_symbol_symbol_and_denom_map = bidict()
        spot_markets_map = {}
        derivative_markets_map = {}
        spot_market_id_to_trading_pair = bidict()
        derivative_market_id_to_trading_pair = bidict()

        async with self.throttler.execute_task(limit_id=CONSTANTS.SPOT_MARKETS_LIMIT_ID):
            markets = await self._query_executor.spot_markets(status="active")

        for market_info in markets:
            try:
                if "/" in market_info["ticker"]:
                    ticker_base, ticker_quote = market_info["ticker"].split("/")
                else:
                    ticker_base = market_info["ticker"]
                    ticker_quote = None
                base_token = self._token_from_market_info(
                    denom=market_info["baseDenom"],
                    token_meta=market_info["baseTokenMeta"],
                    candidate_symbol=ticker_base,
                )
                quote_token = self._token_from_market_info(
                    denom=market_info["quoteDenom"],
                    token_meta=market_info["quoteTokenMeta"],
                    candidate_symbol=ticker_quote,
                )
                market = InjectiveSpotMarket(
                    market_id=market_info["marketId"],
                    base_token=base_token,
                    quote_token=quote_token,
                    market_info=market_info
                )
                spot_market_id_to_trading_pair[market.market_id] = market.trading_pair()
                spot_markets_map[market.market_id] = market
            except KeyError:
                self.logger().debug(f"The spot market {market_info['marketId']} will be excluded because it could not "
                                    f"be parsed ({market_info})")
                continue

        async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_MARKETS_LIMIT_ID):
            markets = await self._query_executor.derivative_markets(status="active")
        for market_info in markets:
            try:
                market = self._parse_derivative_market_info(market_info=market_info)
                if market.trading_pair() in derivative_market_id_to_trading_pair.inverse:
                    self.logger().debug(
                        f"The derivative market {market_info['marketId']} will be excluded because there is other"
                        f" market with trading pair {market.trading_pair()} ({market_info})")
                    continue
                derivative_market_id_to_trading_pair[market.market_id] = market.trading_pair()
                derivative_markets_map[market.market_id] = market
            except KeyError:
                self.logger().debug(f"The derivative market {market_info['marketId']} will be excluded because it could"
                                    f" not be parsed ({market_info})")
                continue

        self._spot_market_info_map = spot_markets_map
        self._spot_market_and_trading_pair_map = spot_market_id_to_trading_pair
        self._derivative_market_info_map = derivative_markets_map
        self._derivative_market_and_trading_pair_map = derivative_market_id_to_trading_pair

    def real_tokens_spot_trading_pair(self, unique_trading_pair: str) -> str:
        resulting_trading_pair = unique_trading_pair
        if (self._spot_market_and_trading_pair_map is not None
                and self._spot_market_info_map is not None):
            market_id = self._spot_market_and_trading_pair_map.inverse.get(unique_trading_pair)
            market = self._spot_market_info_map.get(market_id)
            if market is not None:
                resulting_trading_pair = combine_to_hb_trading_pair(
                    base=market.base_token.symbol,
                    quote=market.quote_token.symbol,
                )

        return resulting_trading_pair

    def real_tokens_perpetual_trading_pair(self, unique_trading_pair: str) -> str:
        resulting_trading_pair = unique_trading_pair
        if (self._derivative_market_and_trading_pair_map is not None
                and self._derivative_market_info_map is not None):
            market_id = self._derivative_market_and_trading_pair_map.inverse.get(unique_trading_pair)
            market = self._derivative_market_info_map.get(market_id)
            if market is not None:
                resulting_trading_pair = combine_to_hb_trading_pair(
                    base=market.base_token_symbol(),
                    quote=market.quote_token.symbol,
                )

        return resulting_trading_pair

    async def order_updates_for_transaction(
            self,
            transaction_hash: str,
            spot_orders: Optional[List[GatewayInFlightOrder]] = None,
            perpetual_orders: Optional[List[GatewayPerpetualInFlightOrder]] = None
    ) -> List[OrderUpdate]:
        raise NotImplementedError

    def supported_order_types(self) -> List[OrderType]:
        return []

    async def _initialize_timeout_height(self):  # pragma: no cover
        # Do nothing
        pass

    def _sign_and_encode(self, transaction: Transaction) -> bytes:
        raise NotImplementedError

    def _uses_default_portfolio_subaccount(self) -> bool:
        raise NotImplementedError

    async def _calculate_order_hashes(
            self,
            spot_orders: List[GatewayInFlightOrder],
            derivative_orders: [GatewayPerpetualInFlightOrder]) -> Tuple[List[str], List[str]]:
        raise NotImplementedError

    def _reset_order_hash_manager(self):
        raise NotImplementedError

    async def _order_creation_messages(
            self,
            spot_orders_to_create: List[GatewayInFlightOrder],
            derivative_orders_to_create: List[GatewayPerpetualInFlightOrder]
    ) -> Tuple[List[any_pb2.Any], List[str], List[str]]:
        raise NotImplementedError

    async def _order_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        raise NotImplementedError

    async def _all_subaccount_orders_cancel_message(
            self,
            spot_orders_to_cancel: List[injective_exchange_tx_pb.OrderData],
            derivative_orders_to_cancel: List[injective_exchange_tx_pb.OrderData]
    ) -> any_pb2.Any:
        raise NotImplementedError

    async def _generate_injective_order_data(
            self,
            order: GatewayInFlightOrder,
            market_id: str,
    ) -> injective_exchange_tx_pb.OrderData:
        raise NotImplementedError

    async def _updated_derivative_market_info_for_id(self, market_id: str) -> InjectiveDerivativeMarket:
        async with self.throttler.execute_task(limit_id=CONSTANTS.DERIVATIVE_MARKETS_LIMIT_ID):
            market_info = await self._query_executor.derivative_market(market_id=market_id)

        market = self._parse_derivative_market_info(market_info=market_info)
        return market

    def _place_order_results(
            self,
            orders_to_create: List[GatewayInFlightOrder],
            order_hashes: List[str],
            misc_updates: Dict[str, Any],
            exception: Optional[Exception] = None
    ) -> List[PlaceOrderResult]:
        raise NotImplementedError

    def _token_from_market_info(
            self, denom: str, token_meta: Dict[str, Any], candidate_symbol: Optional[str] = None
    ) -> InjectiveToken:
        token = self._tokens_map.get(denom)
        if token is None:
            unique_symbol = token_meta["symbol"]
            if unique_symbol in self._token_symbol_symbol_and_denom_map:
                if candidate_symbol is not None and candidate_symbol not in self._token_symbol_symbol_and_denom_map:
                    unique_symbol = candidate_symbol
                else:
                    unique_symbol = token_meta["name"]
            token = InjectiveToken(
                denom=denom,
                symbol=token_meta["symbol"],
                unique_symbol=unique_symbol,
                name=token_meta["name"],
                decimals=token_meta["decimals"]
            )
            self._tokens_map[denom] = token
            self._token_symbol_symbol_and_denom_map[unique_symbol] = denom

        return token

    def _parse_derivative_market_info(self, market_info: Dict[str, Any]) -> InjectiveDerivativeMarket:
        ticker_quote = None
        if "/" in market_info["ticker"]:
            _, ticker_quote = market_info["ticker"].split("/")
        quote_token = self._token_from_market_info(
            denom=market_info["quoteDenom"],
            token_meta=market_info["quoteTokenMeta"],
            candidate_symbol=ticker_quote,
        )
        market = InjectiveDerivativeMarket(
            market_id=market_info["marketId"],
            quote_token=quote_token,
            market_info=market_info
        )
        return market

    async def _listen_to_positions_updates(self):  # pragma: no cover
        # Do nothing
        pass

    async def _listen_to_account_balance_updates(self):  # pragma: no cover
        # Do nothing
        pass

    async def _listen_to_subaccount_spot_order_updates(self, market_id: str):  # pragma: no cover
        # Do nothing
        pass

    async def _listen_to_subaccount_derivative_order_updates(self, market_id: str):  # pragma: no cover
        # Do nothing
        pass
