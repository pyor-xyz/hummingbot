from typing import AsyncGenerator, Dict, Optional

import socketio

from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse


class SocketIoAssistant:
    """A helper class to contain all WebSocket-related logic.
    """

    def __init__(self):
        self._sio = socketio.Client()

    @property
    def last_recv_time(self) -> float:
        pass

    async def connect(
        self,
        ws_url: str,
        *,
        ping_timeout: float = 10,
        message_timeout: Optional[float] = None,
        ws_headers: Optional[Dict] = {},
    ):
        await self._sio.connect(ws_url)

    async def disconnect(self):
        await self._sio.disconnect()

    async def send_request(self, request: WSRequest) -> AsyncGenerator[WSResponse, None]:
        for pre_processor in self._ws_pre_processors:
            request = pre_processor.process_request(request)

        await self._sio.emit('message', request.to_dict())

        async def response_generator():
            while True:
                response = await self._sio.call('message')
                response = WSResponse.from_dict(response)

                for post_processor in self._ws_post_processors:
                    response = post_processor.process_response(response)

                yield response

        return response_generator()

    async def subscribe(self, event_name: str, message: Dict):
        await self._sio.emit(event_name, message)

    async def ping(self):
        pass

    async def iter_messages(self) -> AsyncGenerator[Optional[WSResponse], None]:
        while self._sio.connected:
            response = await self._sio.call('message')
            if response is not None:
                response = await self._post_process_response(response)
                yield response

    async def receive(self) -> Optional[WSResponse]:
        response = await self._sio.call('message')
        if response is not None:
            response = await self._post_process_response(response)
        return response

    async def _pre_process_request(self, request: WSRequest) -> WSRequest:
        for pre_processor in self._ws_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: WSRequest) -> WSRequest:
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.ws_authenticate(request)
        return request

    async def _post_process_response(self, response: WSResponse) -> WSResponse:
        for post_processor in self._ws_post_processors:
            response = await post_processor.post_process(response)
        return response
