import logging
from asyncio import sleep, get_event_loop, AbstractEventLoop
from base64 import b64encode
from typing import Coroutine

from grpc import ServicerContext, StatusCode
from grpc.aio import server, Server
from requests import get, post, Response

from oauth_endpoints import OAuthEndpoints
from service.service_pb2 import RevokeRequest, IntrospectRequest, UserInfoRequest, AuthResponse, IntrospectResponse, \
    UserInfoResponse, Empty
from service.service_pb2_grpc import OAuthServiceServicer, add_OAuthServiceServicer_to_server

_CLEANUP_COROUTINES: list[Coroutine] = []


class OAuthService(OAuthServiceServicer):
    """
    Demo OAuth Service that receives gRPC calls that are translated to their respective REST calls.
    """

    APPLICATION_X_WWW_FORM_URLENCODED: str = "application/x-www-form-urlencoded"
    DEVICE_GRANT_TYPE: str = "urn:ietf:params:oauth:grant-type:device_code"

    BASE64_ADMIN_CREDENTIALS: str
    BASE64_CLIENT_CREDENTIALS: str

    def __init__(self, oauth_endpoints: OAuthEndpoints, client_id: str, client_secret: str,
                 admin_username: str = "admin", admin_password: str = "admin") -> None:
        self._oauth_endpoints = oauth_endpoints
        self._client_id = client_id
        self._client_secret = client_secret

        self.BASE64_ADMIN_CREDENTIALS = b64encode(f"{admin_username}:{admin_password}".encode()).decode()
        self.BASE64_CLIENT_CREDENTIALS = b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async def Introspect(self, request: IntrospectRequest, context: ServicerContext) -> IntrospectResponse:
        """
        Makes a request to the Introspection Endpoint to validate the token.

        :param request: gRPC request
        :param context: gRPC context
        :return: gRPC response
        """

        data: dict[str, str] = {
            "token": request.token
        }

        headers: dict[str, str] = {
            "Authorization": f"Basic {self.BASE64_ADMIN_CREDENTIALS}",
            "Content-Type": self.APPLICATION_X_WWW_FORM_URLENCODED
        }

        response: Response = post(
            url=self._oauth_endpoints.introspect,
            data=data,
            headers=headers,
            verify=False
        )

        if response.status_code == 200:
            response_json: dict[str, object] = response.json()
            is_active: object = response_json.get("active", None)

            # Check if 'active' key is present and the expected type
            if isinstance(is_active, str) or isinstance(is_active, bool):
                return IntrospectResponse(active=bool(is_active))
            else:
                await context.abort(
                    StatusCode.INVALID_ARGUMENT,
                    f"Invalid JSON received. Response: {response.content}"
                )
        else:
            await context.abort(StatusCode.INTERNAL, f"Introspection failed. Response: {response.content}")

    async def Revoke(self, request: RevokeRequest, context: ServicerContext) -> Empty:
        """
        Invokes the Token Revoke Endpoint for revoking the informed token and returns its message.

        :param request: gRPC request
        :param context: gRPC context
        :return: gRPC response
        """
        data: dict[str, str] = {
            "token": request.token
        }

        headers: dict[str, str] = {
            "Authorization": f"Basic {self.BASE64_CLIENT_CREDENTIALS}",
            "Content-Type": self.APPLICATION_X_WWW_FORM_URLENCODED
        }

        post(
            url=self._oauth_endpoints.revoke,
            data=data,
            headers=headers,
            verify=False
        )

        return Empty()

    async def UserInfo(self, request: UserInfoRequest, context: ServicerContext) -> UserInfoResponse:
        token: str = request.token

        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}"
        }

        response: Response = get(
            url=self._oauth_endpoints.user_info,
            headers=headers,
            verify=False
        )

        if response.status_code != 200:
            await context.abort(StatusCode.INTERNAL, f"Failed to fetch user info. Response: {response.content}")

        return UserInfoResponse(info=response.text)  # Response is already JSON, no need for conversions

    async def Authenticate(self, request: Empty, context: ServicerContext) -> AuthResponse:
        """
        Attempts to generate an access token from the Identity Provider and return it to the client.
        First response will only include the URL for login, with subsequent responses informing its status.

        :param request: gRPC request
        :param context: gRPC context
        :return: gRPC response
        """
        # Get the device_code, verification_url, and polling_time
        device_code, verification_url, polling_time = await self._get_device_authorization_response(context=context)

        # Send the initial response and wait first tick
        yield AuthResponse(message=f"Go to {verification_url} to complete login")
        await sleep(polling_time)

        # Start polling the authorization server for the access_token
        while True:
            tokens = await self._poll_token_endpoint(device_code=device_code, context=context)
            if tokens is not None:
                access_token, refresh_token = tokens
                yield AuthResponse(
                    message="Success",
                    access_token=access_token,
                    refresh_token=refresh_token
                )
                break
            else:
                yield AuthResponse(message="Waiting for response...")
                await sleep(polling_time)  # wait for 5 seconds before polling again

    async def _poll_token_endpoint(self, device_code, context) -> tuple[str, str] or None:
        """
        Poll the authorization server to check if the user has completed the authentication.

        :param device_code: The device code returned by the Identity Provider during the initial authentication request.
        :return: The token if the user has completed the authentication, None otherwise.
        """

        data: dict[str, str] = {
            "client_id": self._client_id,
            "device_code": device_code,
            "grant_type": self.DEVICE_GRANT_TYPE,
        }

        headers: dict[str, str] = {
            "Content-Type": self.APPLICATION_X_WWW_FORM_URLENCODED
        }

        response: Response = post(
            url=f"{self._oauth_endpoints.token}?scope=openid",
            data=data,
            headers=headers,
            verify=False
        )

        if response.status_code == 200:
            response_json: dict[str, object] = response.json()

            access_token: str = response_json.get("access_token", None)
            refresh_token: str = response_json.get("refresh_token", None)

            return access_token, refresh_token

        elif response.status_code == 400:
            return None

        else:
            await context.abort(
                StatusCode.INTERNAL,
                f"Unexpected response from Identity Provider: {response.content}"
            )
            return None

    async def _get_device_authorization_response(self, context: ServicerContext) -> tuple[str, str, int] or None:
        """
        Attempts to get device code from device_authorize endpoint.

        :return: tuple containing (device_code, verification_uri, polling_time_seconds)
        """

        data: dict[str, str] = {
            "client_id": self._client_id
        }

        headers: dict[str, str] = {
            "Content-Type": self.APPLICATION_X_WWW_FORM_URLENCODED
        }

        response: Response = post(
            url=f"{self._oauth_endpoints.device_authorize}?scope=openid",
            data=data,
            headers=headers,
            verify=False
        )

        if response.status_code == 200:
            json_response: dict[str, object] = response.json()

            device_code: str = json_response.get("device_code", None)
            polling_time_seconds: int = int(json_response.get("interval", 5))

            # Use URL with embedded user_code
            verification_url: str = json_response.get("verification_uri_complete", None)

            return device_code, verification_url, polling_time_seconds
        else:
            await context.abort(
                StatusCode.INTERNAL,
                f"Unexpected behaviour when retrieving device code. Response: {response.content}"
            )
            return None


async def server_graceful_shutdown(aio_server: Server) -> None:
    logging.info("Shutting down...")
    await aio_server.stop(5)


async def serve() -> None:
    is_host: str = "localhost"
    is_port: int = 9443
    listen_addr: str = "localhost:50051"

    aio_server: Server = server()

    add_OAuthServiceServicer_to_server(
        servicer=OAuthService(
            oauth_endpoints=OAuthEndpoints(
                device_authorize=f"https://{is_host}:{is_port}/oauth2/device_authorize",
                token=f"https://{is_host}:{is_port}/oauth2/token",
                introspect=f"https://{is_host}:{is_port}/oauth2/introspect",
                revoke=f"https://{is_host}:{is_port}/oauth2/revoke",
                user_info=f"https://{is_host}:{is_port}/oauth2/userinfo"
            ),
            client_id="8p4o4oO_xK7wtSlfTYMQSCZfwwca",
            client_secret="UFBCRGpbxDrjq7EHM9Hxu1w7wVAa"
        ),
        server=aio_server
    )

    aio_server.add_insecure_port(listen_addr)
    logging.info("Starting server on %s", listen_addr)
    await aio_server.start()

    _CLEANUP_COROUTINES.append(server_graceful_shutdown(aio_server=aio_server))
    await aio_server.wait_for_termination()


if __name__ == "__main__":
    loop: AbstractEventLoop = get_event_loop()
    try:
        loop.run_until_complete(serve())
    finally:
        loop.close()
