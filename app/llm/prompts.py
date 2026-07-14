RESPONSE_FORMAT = {
    "type": "object",
    "properties": {
        "item": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "natural_answer": {"type": "string"},
                        "tools_used": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "layouts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "data": {
                                        "type": "object",
                                        "additionalProperties": False,
                                    },
                                    "actions": {
                                        "anyOf": [
                                            {
                                                "type": "object",
                                                "additionalProperties": False,
                                            },
                                            {"type": "null"},
                                        ]
                                    },
                                },
                                "required": ["type", "data", "actions"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": [
                        "natural_answer",
                        "tools_used",
                        "layouts",
                    ],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "detail": {"type": "string"},
                    },
                    "required": ["detail"],
                    "additionalProperties": False,
                },
            ],
        }
    },
    "required": ["item"],
    "additionalProperties": False,
}