package com.qacart.todo.steps.utils.reporting;

import org.monte.media.Format;
import org.monte.media.math.Rational;
import org.monte.screenrecorder.ScreenRecorder;

import java.awt.*;
import java.io.File;

import static org.monte.media.AudioFormatKeys.*;
import static org.monte.media.VideoFormatKeys.*;

public class VideoRecorder {

  private static ScreenRecorder recorder;
  private static File videoDir;

  public static void start(String scenarioName) {
    try {
      videoDir = new File("target/videos");
      videoDir.mkdirs();

      GraphicsConfiguration gc = GraphicsEnvironment
          .getLocalGraphicsEnvironment()
          .getDefaultScreenDevice()
          .getDefaultConfiguration();

      recorder = new ScreenRecorder(
          gc,
          gc.getBounds(),
          new Format(MediaTypeKey, MediaType.FILE, MimeTypeKey, MIME_AVI),
          new Format(MediaTypeKey, MediaType.VIDEO, EncodingKey, ENCODING_AVI_TECHSMITH_SCREEN_CAPTURE,
              CompressorNameKey, ENCODING_AVI_TECHSMITH_SCREEN_CAPTURE,
              DepthKey, 24, FrameRateKey, Rational.valueOf(15),
              QualityKey, 1.0f,
              KeyFrameIntervalKey, 15 * 60),
          new Format(MediaTypeKey, MediaType.VIDEO, EncodingKey, "black",
              FrameRateKey, Rational.valueOf(30)),
          new Format(MediaTypeKey, MediaType.AUDIO, EncodingKey, ENCODING_PCM_SIGNED,
              SampleRateKey, Rational.valueOf(44100),
              SampleSizeInBitsKey, 16,
              ChannelsKey, 2, FrameRateKey, Rational.valueOf(30)),
          videoDir
      );

      recorder.start();

    } catch (Exception e) {
      AllureAttachments.addText("VIDEO START ERROR", e.toString());
    }
  }

  public static File stop() {
    try {
      if (recorder != null) {
        recorder.stop();
        // Monte écrit le fichier dans videoDir, on récupère le dernier fichier
        File[] files = videoDir.listFiles();
        if (files != null && files.length > 0) {
          // retourne le plus récent
          File latest = files[0];
          for (File f : files) if (f.lastModified() > latest.lastModified()) latest = f;
          return latest;
        }
      }
    } catch (Exception e) {
      AllureAttachments.addText("VIDEO STOP ERROR", e.toString());
    }
    return null;
  }
}