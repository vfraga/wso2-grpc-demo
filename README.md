# wso2-grpc-demo


For Unix systems, you can export a `PROJECT_HOME` environment variable to help you throughout the installation. Run this from your project home directory:
```
export PROJECT_HOME=`pwd`
```

---
## Python

Create a Python Virtual Environment for the project (Python >= 3.9):
```
python -m venv $PROJECT_HOME/python/venv
```
Activate the venv:
```
source $PROJECT_HOME/python/venv/bin/activate
```
Install the dependencies:
```
pip install -r $PROJECT_HOME/python/requirements.txt
```
Generate the protobuf classes:
```
python -m grpc_tools.protoc -I $PROJECT_HOME/protos --python_out=$PROJECT_HOME/python/service --pyi_out=$PROJECT_HOME/python/service --grpc_python_out=$PROJECT_HOME/python/service $PROJECT_HOME/protos/service.proto
```
* If you get an `ModuleNotFound` error, check if `$PROJECT_HOME/python/service/service_pb2_grpc.py` correctly imports `service_pb2`. It should be: `import service.service_pb2 as service__pb2`. I'm not sure why this happens.

Run the server:
```
python $PROJECT_HOME/python/server.py
```

Run the client:
```
python $PROJECT_HOME/python/client.py
```

---
## Java

### Requirements:
- Maven >= 3.6
- Java 11

From `$PROJECT_HOME/java` run:
```
mvn clean install
```
Run the client:
```
java -jar $PROJECT_HOME/java/target/oauth-client-1.0-SNAPSHOT.jar
```

---
## Javascript

From `$PROJECT_HOME/javascript` run:
```
npm install
```

Execute the client by running:
```
node ./index.js
```
