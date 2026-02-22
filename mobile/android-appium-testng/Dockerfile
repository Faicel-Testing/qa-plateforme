FROM maven:3.9.6-eclipse-temurin-17

WORKDIR /app

COPY pom.xml .
RUN mvn -B -q -DskipTests dependency:go-offline

COPY src ./src
COPY testng.xml .
COPY QAcart-To-Do.apk /app/QAcart-To-Do.apk
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
