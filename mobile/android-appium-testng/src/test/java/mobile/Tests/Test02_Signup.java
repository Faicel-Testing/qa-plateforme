package mobile.Tests;
import org.testng.annotations.Test;
import org.testng.annotations.Test;

import mobile.core.BaseTest;
import mobile.pages.Test02_SignupPage;

public class Test02_Signup extends BaseTest {

    @Test(groups = {"regression", "quarantine"})
    public void signup() {

        new Test02_SignupPage(getDriver())
                .goToSignupScreen()
                .waitForSignupForm()
                .fillSignupForm()
                .submitSignup();
    }   

}

