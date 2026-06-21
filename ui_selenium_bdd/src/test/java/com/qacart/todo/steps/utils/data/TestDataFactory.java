package com.qacart.todo.steps.utils.data;

import com.qacart.todo.data.User;

public final class TestDataFactory {

    private TestDataFactory() {}

    public static User randomUser() {
        long ts  = System.currentTimeMillis();
        int  num = (int)(ts % 9000) + 1000;
        return new User(
            "Test",
            "User",
            "user" + ts + "@mail.com",
            "Test" + num + "!"
        );
    }
}
