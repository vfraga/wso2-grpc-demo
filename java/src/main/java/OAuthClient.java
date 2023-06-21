import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.core.config.Configurator;

import service.OAuthServiceGrpc;
import service.OAuthServiceGrpc.OAuthServiceBlockingStub;
import service.Service.AuthResponse;
import service.Service.Empty;
import service.Service.IntrospectRequest;
import service.Service.IntrospectResponse;
import service.Service.RevokeRequest;
import service.Service.UserInfoRequest;
import service.Service.UserInfoResponse;

import java.util.Iterator;

public class OAuthClient {

    static {
        Configurator.setLevel(OAuthClient.class, Level.INFO);
    }

    private static final Logger logger = LogManager.getLogger(OAuthClient.class);

    public static void main(final String[] args) {

        final ManagedChannel channel = ManagedChannelBuilder
                .forAddress("localhost", 50051)
                .usePlaintext()
                .build();

        final OAuthServiceBlockingStub stub = OAuthServiceGrpc.newBlockingStub(channel);

        final Iterator<AuthResponse> authResponseIterator = stub.authenticate(Empty.newBuilder().build());

        // Get initial response before looping
        AuthResponse authResponse = authResponseIterator.next();
        logger.info(authResponse.getMessage());


        while (authResponseIterator.hasNext()) {
            authResponse = authResponseIterator.next();
            logger.info(authResponse.getMessage());
        }

        // Get the access and refresh token from the last message streamed
        final String accessToken = authResponse.getAccessToken();
        final String refreshToken = authResponse.getRefreshToken();

        // Check if token is valid
        IntrospectResponse introspectResponse = stub.introspect(
                IntrospectRequest.newBuilder()
                        .setToken(accessToken)
                        .build()
        );

        logger.info("Introspect successful. Token " + accessToken + " is " + (introspectResponse.getActive() ? "active" : "inactive"));

        // Get user info using token received
        UserInfoResponse userInfoResponse = stub.userInfo(
                UserInfoRequest.newBuilder()
                        .setToken(accessToken)
                        .build()
        );

        logger.info("Received User Info: " + userInfoResponse.getInfo());

        // Revokes token and call Introspect to double-check
        Empty ignored = stub.revoke(RevokeRequest.newBuilder().setToken(accessToken).build());

        introspectResponse = stub.introspect(
                IntrospectRequest.newBuilder()
                        .setToken(accessToken)
                        .build()
        );

        logger.info("Token " + accessToken + " was revoked. Introspect says token is " + (introspectResponse.getActive() ? "active" : "inactive"));

        channel.shutdown();
    }
}
