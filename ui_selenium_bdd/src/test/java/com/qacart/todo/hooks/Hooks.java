package com.qacart.todo.hooks;

import com.qacart.todo.factory.DriverService;
import com.qacart.todo.steps.utils.reporting.AllureAttachments;
import com.qacart.todo.steps.utils.reporting.ExecutorWriter;
import com.qacart.todo.steps.utils.reporting.VideoRecorder; // ✅ décommente si tu ajoutes VideoRecorder
import io.cucumber.java.After;
import io.cucumber.java.AfterStep;
import io.cucumber.java.Before;
import io.cucumber.java.Scenario;

import java.io.File;

public class Hooks {

  @Before
  public void before(Scenario scenario) {
    // ✅ build metadata for Allure (Trend/Executors)
    try {
      ExecutorWriter.writeExecutor();
    } catch (Exception e) {
      // ne bloque jamais le scénario
    }

    DriverService.start();

    // ✅ preuve hook + meta
    AllureAttachments.addText("HOOK BEFORE", "Scenario: " + scenario.getName());

    // ✅ Video (optionnel)
     //VideoRecorder.start(scenario.getName());
  }

  /**
   * Screenshot automatique à chaque step uniquement si le scénario est FAIL.
   * (Cucumber marque le scenario failed dès qu’une step échoue)
   */
  @AfterStep
  public void afterStep(Scenario scenario) {
    if (!scenario.isFailed()) return;

    try {
      AllureAttachments.addScreenshot("Failure Screenshot (AfterStep)");
      AllureAttachments.addUrl("Failure URL (AfterStep)");
    } catch (Exception e) {
      AllureAttachments.addText("AFTER STEP ERROR", e.toString());
    }
  }

  @After
  public void after(Scenario scenario) {

    try {
      // ✅ texte toujours
      AllureAttachments.addText("HOOK AFTER", "Status=" + scenario.getStatus());

      // ✅ artifacts utiles pour RCA
      try {
        AllureAttachments.addFile("Framework log", "target/logs/framework.log", "text/plain", ".log");
      } catch (Exception e) {
        AllureAttachments.addText("LOG ATTACH ERROR", e.toString());
      }

      try {
        AllureAttachments.addDriverInfo();
      } catch (Exception e) {
        AllureAttachments.addText("DRIVER INFO ERROR", e.toString());
      }

      try {
        AllureAttachments.addBrowserConsoleLogs();
      } catch (Exception e) {
        AllureAttachments.addText("BROWSER LOGS ERROR", e.toString());
      }

      // ✅ screenshot + page source : recommande “only on fail” (sinon lourd)
      if (scenario.isFailed()) {
        try {
          AllureAttachments.addUrl("URL");
          AllureAttachments.addScreenshot("Screenshot");
          AllureAttachments.addPageSource("Page Source");
        } catch (Exception e) {
          AllureAttachments.addText("ATTACHMENT ERROR", e.toString());
        }
      }

      // ✅ Video (optionnel) : attacher uniquement si FAIL
       //try {
        // File video = VideoRecorder.stop();
        // if (scenario.isFailed() && video != null) {
        //   AllureAttachments.addFile("Video", video.getPath(), "video/avi", ".avi");
        // } else if (video != null) {
        // si tu ne veux pas conserver les vidéos PASS
         //  video.delete();
         //}
      // } catch (Exception e) {
        // AllureAttachments.addText("VIDEO ERROR", e.toString());
      // }

    } finally {
      DriverService.stop();
    }
  }
}