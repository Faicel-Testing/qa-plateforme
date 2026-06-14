package com.qacart.todo.steps.utils;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.Properties;

public class ConfigUtil {
    // Le rôle de cette méthode est de lire à partir de properties et nous retourne le prop file
public static Properties readConfig(String path) throws IOException {
    File propFile = new File(path);
    FileInputStream is = new FileInputStream(propFile);
    //Son rôle est de lire à partir des files
    Properties prop = new Properties();
    prop.load(is);
    //Pour fermer le FileinputStream
    is.close();
    return prop;
}
}
