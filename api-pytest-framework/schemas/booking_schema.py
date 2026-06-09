BOOKING_SCHEMA = {
    "type": "object",
    "required": ["firstname", "lastname", "totalprice", "depositpaid", "bookingdates"],
    "properties": {
        "firstname":       {"type": "string"},
        "lastname":        {"type": "string"},
        "totalprice":      {"type": "integer"},
        "depositpaid":     {"type": "boolean"},
        "additionalneeds": {"type": "string"},
        "bookingdates": {
            "type": "object",
            "required": ["checkin", "checkout"],
            "properties": {
                "checkin":  {"type": "string"},
                "checkout": {"type": "string"},
            }
        }
    }
}

CREATE_BOOKING_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["bookingid", "booking"],
    "properties": {
        "bookingid": {"type": "integer"},
        "booking":   BOOKING_SCHEMA,
    }
}

BOOKING_ID_SCHEMA = {
    "type": "object",
    "required": ["bookingid"],
    "properties": {
        "bookingid": {"type": "integer"}
    }
}

AUTH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["token"],
    "properties": {
        "token": {"type": "string"}
    }
}
