package com.restfulbooker.steps;

import com.restfulbooker.client.AuthClient;
import com.restfulbooker.client.BookingClient;
import com.restfulbooker.context.ScenarioContext;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.path.json.JsonPath;

import java.util.List;
import java.util.Map;

import static org.testng.Assert.*;

/**
 * Steps partagés par toutes les features BDD (Background + Then communs).
 * Équivalent Java de features/steps/common_steps.py.
 */
public class CommonSteps {

    private final ScenarioContext ctx;

    public CommonSteps(ScenarioContext ctx) {
        this.ctx = ctx;
    }

    // ── Background commun ────────────────────────────────────────────────────

    @Given("^l'API est disponible$")
    public void apiDisponible() {
        ctx.setAuth(new AuthClient());
        ctx.setBooking(new BookingClient());
    }

    @Given("^j'ai un token d'authentification valide$")
    public void tokenValide() {
        String token = ctx.getAuth().getToken();
        ctx.setToken(token);
        ctx.setBooking(new BookingClient(token));
    }

    @Given("^une reservation existe avec un ID valide$")
    public void reservationValideId() {
        var resp = ctx.getBooking().createBooking();
        ctx.setBookingId(resp.jsonPath().getInt("bookingid"));
    }

    @Given("^une reservation existe avec son ID$")
    public void reservationAvecId() {
        var resp = ctx.getBooking().createBooking();
        ctx.setBookingId(resp.jsonPath().getInt("bookingid"));
    }

    @Given("^j'ai cree une reservation et recupere son ID$")
    public void reservationCreeId() {
        var resp = ctx.getBooking().createBooking();
        ctx.setBookingId(resp.jsonPath().getInt("bookingid"));
    }

    @Given("^j'ai supprime la reservation avec succes$")
    public void reservationSupprimee() {
        if (ctx.getBookingId() == null) {
            var resp = ctx.getBooking().createBooking();
            ctx.setBookingId(resp.jsonPath().getInt("bookingid"));
        }
        ctx.getBooking().deleteBooking(ctx.getBookingId());
    }

    // ── When : GET /booking/{id} (partagé get / update / delete) ────────────

    @When("^j'envoie GET /booking/\\{id\\}$")
    public void getBookingByIdCommon() {
        ctx.setResponse(ctx.getBooking().getBooking(ctx.getBookingId()));
    }

    // ── Then : status code ────────────────────────────────────────────────────

    @Then("^le status code est (\\d+)$")
    public void checkStatus(int code) {
        var resp = ctx.getResponse();
        assertEquals(resp.statusCode(), code,
                "Attendu HTTP " + code + ", recu " + resp.statusCode() + " -- " + safeBody(resp));
    }

    @Then("^le status code est (\\d+) ou (\\d+)$")
    public void checkStatusOr(int c1, int c2) {
        var resp = ctx.getResponse();
        assertTrue(resp.statusCode() == c1 || resp.statusCode() == c2,
                "Attendu HTTP " + c1 + " ou " + c2 + ", recu " + resp.statusCode() + " -- " + safeBody(resp));
    }

    // ── Then : securite ───────────────────────────────────────────────────────

    @Then("^le payload est encode ou refuse -- aucune execution$")
    public void payloadNonExecute() {
        String body = ctx.getResponse().getBody().asString().toLowerCase();
        assertFalse(body.contains("<script>"), "XSS non filtre dans la reponse : " + body);
    }

    // ── Then : champ bookingid (partagé create / list) ───────────────────────

    @Then("^la reponse contient un champ \"bookingid\" entier > 0$")
    public void checkBookingIdPositive() {
        var resp = ctx.getResponse();
        JsonPath json = resp.jsonPath();
        Object root = json.get("$");
        if (root instanceof List<?> list) {
            assertFalse(list.isEmpty(), "La liste est vide");
            for (Object item : list) {
                Map<?, ?> map = (Map<?, ?>) item;
                Number bookingid = (Number) map.get("bookingid");
                assertTrue(bookingid != null && bookingid.intValue() > 0,
                        "bookingid invalide dans : " + item);
            }
        } else {
            Integer bookingid = json.getInt("bookingid");
            assertTrue(bookingid != null && bookingid > 0, "bookingid invalide : " + bookingid);
        }
    }

    // ── Then : champs et données (partagé create / get / update) ────────────

    @Then("^la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates$")
    public void checkBookingFieldsCommon() {
        JsonPath json = ctx.getResponse().jsonPath();
        // POST /booking imbrique sous "booking", GET /booking/{id} est direct
        String prefix = json.get("booking") != null ? "booking." : "";
        for (String field : new String[]{"firstname", "lastname", "totalprice", "depositpaid", "bookingdates"}) {
            assertNotNull(json.get(prefix + field), "Champ '" + field + "' absent dans la reponse");
        }
    }

    @Then("^la reponse contient les donnees mises a jour$")
    public void checkUpdatedDataCommon() {
        JsonPath json = ctx.getResponse().jsonPath();
        assertEquals(json.getString("firstname"), "UpdatedJim", "firstname non mis a jour");
        assertEquals(json.getInt("totalprice"), 999, "totalprice non mis a jour");
    }

    // ── Then : corps de la reponse ────────────────────────────────────────────

    @Then("^le body de la reponse contient \"Created\"$")
    public void checkBodyCreated() {
        assertTrue(ctx.getResponse().getBody().asString().contains("Created"),
                "'Created' absent de la reponse : " + safeBody(ctx.getResponse()));
    }

    // ── Then : 404 ────────────────────────────────────────────────────────────

    @Then("^la reponse est 404 Not Found$")
    public void check404Body() {
        assertEquals(ctx.getResponse().statusCode(), 404,
                "Attendu 404, recu " + ctx.getResponse().statusCode());
    }

    private static String safeBody(io.restassured.response.Response resp) {
        String body = resp.getBody().asString();
        return body.length() > 300 ? body.substring(0, 300) : body;
    }
}
