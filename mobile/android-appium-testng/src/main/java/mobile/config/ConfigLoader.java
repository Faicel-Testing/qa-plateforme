package mobile.config;

import java.io.InputStream;
import java.util.Properties;

public class ConfigLoader {

    private static final Properties props = new Properties();

    static {
        try (InputStream is = ConfigLoader.class
                .getClassLoader()
                .getResourceAsStream("config.properties")) {

            if (is == null) {
                throw new RuntimeException("config.properties introuvable dans src/test/resources");
            }

            props.load(is);

        } catch (Exception e) {
            throw new RuntimeException("Erreur chargement config.properties", e);
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

        // 3️⃣ fallback config.properties
        String val = props.getProperty(key);
        if (val == null || val.isBlank()) {
            throw new RuntimeException("Clé manquante: " + key);
        }

        return val.trim();
    }

    public static boolean getBool(String key) {
        return Boolean.parseBoolean(get(key));
    }

    public static int getInt(String key) {
        return Integer.parseInt(get(key));
    }
}