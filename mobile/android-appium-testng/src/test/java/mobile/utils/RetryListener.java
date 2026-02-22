package mobile.utils;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

import org.testng.IAnnotationTransformer;
import org.testng.annotations.ITestAnnotation;

public class RetryListener implements IAnnotationTransformer {

    @Override
    public void transform(ITestAnnotation annotation,
                          Class testClass,
                          Constructor testConstructor,
                          Method testMethod) {

        // On essaye setRetryAnalyzerClass(...) puis setRetryAnalyzer(...)
        try {
            Method m = annotation.getClass().getMethod("setRetryAnalyzerClass", Class.class);
            m.invoke(annotation, RetryAnalyzer.class);
            return;
        } catch (NoSuchMethodException ignored) {
            // continue
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        try {
            Method m = annotation.getClass().getMethod("setRetryAnalyzer", Class.class);
            m.invoke(annotation, RetryAnalyzer.class);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
