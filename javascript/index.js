const PROTO_PATH = __dirname.split('/').slice(0, -1).join('/') + "/protos/service.proto";
// Get PROJECT_HOME path by getting javascript dir and removing one level

const grpc = require("@grpc/grpc-js");
const protoLoader = require("@grpc/proto-loader");

const packageDefinition = protoLoader.loadSync(
  PROTO_PATH,
  {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
  }
);

const service = grpc.loadPackageDefinition(packageDefinition).oauthservice;

const throw_if_error = (error) =>  {
  if (error) throw new Error(error);
}

function main() {
  const client = new service.OAuthService("localhost:50051", grpc.credentials.createInsecure());

  const responseStream = client.Authenticate({});
  let accessToken = null;
  let refreshToken = null;

  responseStream.on("data", function (response) {
      console.log(response.message);

      accessToken = response.access_token;
      refreshToken = response.refresh_token;
    }
  );

  responseStream.on("end", function (error, response) {
      throw_if_error(error);

      client.Introspect({token: accessToken}, function (error, response) {
          throw_if_error(error);

          console.log("Introspect successful. Token " + accessToken + " is " + (response.active ? "active" : "inactive"));
        }
      );

      client.UserInfo({token: accessToken}, function (error, response) {
          throw_if_error(error);

          console.log("Received User Info: " + response.info);
        }
      );

      client.Revoke({token: accessToken}, function (error, response) {
          throw_if_error(error);

          client.Introspect({token: accessToken}, function (error, response) {
              throw_if_error(error);

              console.log("Token " + accessToken + " was revoked. Introspect says token is " + (response.active ? "active" : "inactive"));
            }
          );
        }
      );
    }
  )
}

main();
