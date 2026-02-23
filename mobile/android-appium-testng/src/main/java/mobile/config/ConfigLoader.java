package mobile.config;

import java.io.InputStream;
import java.util.Properties;

public class ConfigLoader {

    private static final Properties baseProps = new Properties();
    private static final Properties envProps  = new Properties();

    static {
        // 1) Charger config.properties (base)
        loadProperties(baseProps, "config.properties", true);

        // 2) Charger config-{env}.properties (override), si env défini
        String env = resolveEnv(); // qa / staging / ...
        if (env != null && !env.isBlank()) {
            String envFile = "config-" + env.trim().toLowerCase() + ".properties";
            loadProperties(envProps, envFile, false); // false => optionnel
        }
    }

    private static void loadProperties(Properties target, String resourceName, boolean required) {
        try (InputStream is = ConfigLoader.class.getClassLoader().getResourceAsStream(resourceName)) {
            if (is == null) {
                if (required) {
                    throw new RuntimeException(resourceName + " introuvable dans src/test/resources");
                }
                return; // optionnel: ne rien faire
            }
            target.load(is);
        } catch (Exception e) {
            throw new RuntimeException("Erreur chargement " + resourceName, e);
        }
    }

    private static String resolveEnv() {
        // Priorité: -Denv=qa | staging
        String sysEnv = System.getProperty("env");
        if (sysEnv != null && !sysEnv.isBlank()) {
            return sysEnv.trim();
        }

        // Variable d'environnement: ENV
        String osEnv = System.getenv("ENV");
        if (osEnv != null && !osEnv.isBlank()) {
            return osEnv.trim();
        }

        // Option: si tu veux un default (ex: qa), décommente:
        // return "qa";

        return null;
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

        // 3️⃣ priorité config-<env>.properties (override) si présent
        String envFileVal = envProps.getProperty(key);
        if (envFileVal != null && !envFileVal.isBlank()) {
            return envFileVal.trim();
        }

        // 4️⃣ fallback config.properties
        String val = baseProps.getProperty(key);
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