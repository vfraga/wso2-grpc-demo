import asyncio
import logging

from grpc.aio import insecure_channel

from service.service_pb2 import AuthResponse, Empty, UserInfoResponse, UserInfoRequest, IntrospectRequest, \
    IntrospectResponse, RevokeRequest
from service.service_pb2_grpc import OAuthServiceStub


async def run() -> None:
    async with insecure_channel('localhost:50051') as channel:
        stub = OAuthServiceStub(channel)

        response: AuthResponse  # typing annotation to help IDE autocompletion
        async for response in stub.Authenticate(Empty()):
            logging.info(response.message)  # prints incoming stream messages

        # Retrieves access and refresh token from last message streamed
        access_token, refresh_token = (response.access_token, response.refresh_token)

        # Check if token is valid
        response: IntrospectResponse = await stub.Introspect(
            IntrospectRequest(token=access_token)
        )

        logging.info("Introspect successful. Token %s is %s",
                     access_token,
                     "active" if response.active else "inactive"
                     )

        # Get user info using token received
        response: UserInfoResponse = await stub.UserInfo(
            UserInfoRequest(token=access_token)
        )

        logging.info("Received User Info: %s", response.info)

        # Revokes token and call Introspect to double-check
        await stub.Revoke(RevokeRequest(token=access_token))

        response: IntrospectResponse = await stub.Introspect(
            IntrospectRequest(token=access_token)
        )

        logging.info("Token %s was revoked. Introspect says token is %s",
                     access_token,
                     "active" if response.active else "inactive"
                     )


if __name__ == "__main__":
    logging.basicConfig()
    asyncio.run(run())
