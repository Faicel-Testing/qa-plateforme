package com.qacart.todo.context;

import java.util.HashMap;
import java.util.Map;

public final class TestContext {

    private static final ThreadLocal<Map<String, Object>> TL =
        ThreadLocal.withInitial(HashMap::new);

    private TestContext() {}

    public static void set(String key, Object value) {
        TL.get().put(key, value);
    }

    public static Object get(String key) {
        return TL.get().get(key);
    }

    public static <T> T get(String key, Class<T> type) {
        return type.cast(TL.get().get(key));
    }

    public static boolean contains(String key) {
        return TL.get().containsKey(key);
    }

    public static void clear() {
        TL.get().clear();
    }
}
