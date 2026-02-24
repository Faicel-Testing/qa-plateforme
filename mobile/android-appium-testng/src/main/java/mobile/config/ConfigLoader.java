package mobile.config;

import java.io.InputStream;
import java.util.Properties;

public class ConfigLoader {

    private static final Properties props = new Properties();

    static {
        try {
            // 1) load default config.properties
            try (InputStream is = ConfigLoader.class
                    .getClassLoader()
                    .getResourceAsStream("config.properties")) {

                if (is == null) {
                    throw new RuntimeException("config.properties introuvable dans src/test/resources");
                }
                props.load(is);
            }

            // 2) load env-specific config: config/{env}.properties
            String env = getOptional("env");
            if (env == null || env.isBlank()) {
                env = "qa";
            }
            String envFile = "config/" + env.trim() + ".properties";

            try (InputStream eis = ConfigLoader.class
                    .getClassLoader()
                    .getResourceAsStream(envFile)) {

                if (eis != null) {
                    props.load(eis);
                }
            }

        } catch (Exception e) {
            throw new RuntimeException("Erreur chargement configuration", e);
        }
    }

    public static String get(String key) {

        // 1️⃣ priorité System Property (mvn -Dkey=value)
        String sysProp = System.getProperty(key);
        if (sysProp != null && !sysProp.isBlank()) {
            return sysProp.trim();
        }

        // 2️⃣ priorité Variable d'environnement (KEY en uppercase + underscore)
        String envKey = key.toUpperCase().replace(".", "_");
        String envVal = System.getenv(envKey);
        if (envVal != null && !envVal.isBlank()) {
            return envVal.trim();
        }

        // 3️⃣ fallback properties (merged)
        String val = props.getProperty(key);
        if (val == null || val.isBlank()) {
            throw new RuntimeException("Clé manquante: " + key);
        }

        return val.trim();
    }

    public static String getOptional(String key) {
        try {
            String v = get(key);
            return (v == null || v.isBlank()) ? null : v.trim();
        } catch (Exception e) {
            return null;
        }
    }

    public static boolean getBool(String key) {
        return Boolean.parseBoolean(get(key));
    }

    public static int getInt(String key) {
        return Integer.parseInt(get(key));
    }
}