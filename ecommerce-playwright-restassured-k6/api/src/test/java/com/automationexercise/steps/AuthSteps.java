package com.automationexercise.steps;

import com.automationexercise.config.Config;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

public class AuthSteps {

    private Response response;

    @When("je vérifie la connexion avec l'email {string} et le mot de passe {string}")
    public void verifyLogin(String email, String password) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                    .formParam("email", email)
                    .formParam("password", password)
                .when()
                    .post("/api/verifyLogin");
    }

    @When("je vérifie la connexion sans email avec le mot de passe {string}")
    public void verifyLoginNoEmail(String password) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                    .formParam("password", password)
                .when()
                    .post("/api/verifyLogin");
    }

    @When("je fais un DELETE sur {string}")
    public void deleteRequest(String path) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded")
                .when()
                    .delete(path);
    }

    @When("je récupère les détails de l'utilisateur {string}")
    public void getUserDetail(String email) {
        response = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .queryParam("email", email)
                .when()
                    .get("/api/getUserDetailByEmail");
    }

    @When("je crée un compte avec les données suivantes:")
    public void createAccount(DataTable dataTable) {
        Map<String, String> data = dataTable.asMaps().get(0);
        RequestSpecification req = RestAssured
                .given()
                    .baseUri(Config.BASE_URL)
                    .contentType("application/x-www-form-urlencoded");

        data.forEach(req::formParam);

        response = req.when().post("/api/createAccount");
    }

    @Then("le body contient l'objet {string} avec un email")
    public void checkUserObject(String field) {
        Object user = response.jsonPath().get(field);
        assertThat(user)
                .as("L'objet '%s' doit être présent dans la réponse", field)
                .isNotNull();
    }
}
