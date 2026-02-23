package mobile.Tests;
import org.testng.annotations.Test;
import org.testng.Assert;
import org.testng.annotations.Test;

import io.appium.java_client.android.AndroidDriver;
import mobile.core.BaseTest;
import mobile.pages.Test01_LoginPage;

public class Test01_Login extends BaseTest {

    @Test(groups = {"smoke", "regression"})
    public void openWebApplication() {

        AndroidDriver driver = getDriver(); // ✅ au lieu d'utiliser "driver" directement

        Test01_LoginPage loginPage = new Test01_LoginPage(driver);

        loginPage
                .waitForLoginForm()
                .fillLoginForm()
                .clickLogin();

        Assert.assertTrue(
                loginPage.isLogoDisplayed(),
                "❌ Le logo QXCart est affiché après login"
        );

        System.out.println("✅ Logo QXCart affiché avec succès après login");
    }

   
}
