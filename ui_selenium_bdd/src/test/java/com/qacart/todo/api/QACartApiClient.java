package com.qacart.todo.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.qacart.todo.data.User;
import com.qacart.todo.steps.utils.EnvUtils;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.cert.X509Certificate;
import java.time.Duration;

/**
 * Client HTTP léger (java.net.http — Java 17 built-in, zéro dépendance ajoutée)
 * pour créer / authentifier des utilisateurs QACart via REST API.
 *
 * Pattern Senior : les préconditions de test ne passent jamais par l'UI.
 *   POST /api/v1/users/register  → crée l'utilisateur en base
 *   POST /api/v1/users/login     → retourne le JWT (utilisé pour les appels API)
 */
public class QACartApiClient {

    private static final HttpClient HTTP = buildHttpClient();

    private static HttpClient buildHttpClient() {
        try {
            // Trust-all pour proxy corporate qui intercepte SSL (même raison que git -c http.sslVerify=false)
            TrustManager[] trustAll = new TrustManager[]{new X509TrustManager() {
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                public void checkClientTrusted(X509Certificate[] c, String a) {}
                public void checkServerTrusted(X509Certificate[] c, String a) {}
            }};
            SSLContext ctx = SSLContext.getInstance("TLS");
            ctx.init(null, trustAll, new java.security.SecureRandom());
            return HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(30))
                    .sslContext(ctx)
                    .build();
        } catch (Exception e) {
            throw new RuntimeException("QACartApiClient — cannot build HTTP client: " + e.getMessage(), e);
        }
    }
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private String baseUrl() {
        try {
            return EnvUtils.getInstance().getURL();
        } catch (Exception e) {
            throw new RuntimeException("QACartApiClient — cannot read BASE_URL: " + e.getMessage(), e);
        }
    }

    /**
     * Crée un nouvel utilisateur via API.
     * @return JWT token renvoyé par l'API après création
     */
    public String register(User user) {
        try {
            ObjectNode body = MAPPER.createObjectNode();
            body.put("firstName", user.firstName);
            body.put("lastName",  user.lastName);
            body.put("email",     user.email);
            body.put("password",  user.password);

            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl() + "/api/v1/users/register"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                    .timeout(Duration.ofSeconds(30))
                    .build();

            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());

            if (res.statusCode() != 201 && res.statusCode() != 200) {
                throw new RuntimeException(
                        "POST /api/v1/users/register → HTTP " + res.statusCode() + "\n" + res.body());
            }

            JsonNode json = MAPPER.readTree(res.body());
            return json.has("token") ? json.get("token").asText() : "";

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("API register error: " + e.getMessage(), e);
        }
    }

    /**
     * Authentifie un utilisateur existant via API.
     * @return JWT token
     */
    public String login(User user) {
        try {
            ObjectNode body = MAPPER.createObjectNode();
            body.put("email",    user.email);
            body.put("password", user.password);

            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl() + "/api/v1/users/login"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                    .timeout(Duration.ofSeconds(30))
                    .build();

            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());

            if (res.statusCode() != 200) {
                throw new RuntimeException(
                        "POST /api/v1/users/login → HTTP " + res.statusCode() + "\n" + res.body());
            }

            JsonNode json = MAPPER.readTree(res.body());
            return json.has("token") ? json.get("token").asText() : "";

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("API login error: " + e.getMessage(), e);
        }
    }
}
