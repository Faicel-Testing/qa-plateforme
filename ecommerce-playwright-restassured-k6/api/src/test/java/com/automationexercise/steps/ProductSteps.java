package com.automationexercise.steps;

import com.automationexercise.config.Config;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.RestAssured;
import io.restassured.response.Response;

import static org.assertj.core.api.Assertions.assertThat;

public class ProductSteps {

    private Response response;

    @When("je fais un GET sur {string}")
    public void getRequest(String path) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                .when()
                    .get(path);
    }

    @When("je fais un POST sur {string} sans body")
    public void postRequestNoBody(String path) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                .when()
                    .post(path);
    }

    @When("je fais un PUT sur {string} sans body")
    public void putRequestNoBody(String path) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                .when()
                    .put(path);
    }

    @When("je recherche le produit {string} via l'API")
    public void searchProduct(String query) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                    .formParam("search_product", query)
                .when()
                    .post("/api/searchProduct");
    }

    @Then("le status code est {int}")
    public void checkStatusCode(int expected) {
        assertThat(response.getStatusCode()).isEqualTo(expected);
    }

    @Then("le body contient {string} égal à {int}")
    public void checkResponseCode(String field, int expected) {
        int actual = response.jsonPath().getInt(field);
        assertThat(actual)
                .as("Champ '%s' attendu: %d, obtenu: %d", field, expected, actual)
                .isEqualTo(expected);
    }

    @Then("le body contient une liste {string} non vide")
    public void checkListNotEmpty(String listName) {
        var list = response.jsonPath().getList(listName);
        assertThat(list)
                .as("La liste '%s' ne doit pas être vide", listName)
                .isNotNull()
                .isNotEmpty();
    }

    @Then("le body contient {string} avec {string}")
    public void checkFieldContains(String field, String expectedText) {
        String actual = response.jsonPath().getString(field);
        assertThat(actual)
                .as("Champ '%s' doit contenir '%s'", field, expectedText)
                .containsIgnoringCase(expectedText);
    }

    @Then("les produits retournés contiennent le terme {string}")
    public void checkProductsContainTerm(String term) {
        var products = response.jsonPath().getList("products.name");
        assertThat(products)
                .as("Les produits doivent contenir le terme '%s'", term)
                .isNotEmpty();
    }
}
