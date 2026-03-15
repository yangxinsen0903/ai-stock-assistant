import re


class RiskGuard:
    banned_patterns = [
        r"guaranteed return",
        r"zero risk",
        r"all in",
        r"sell everything",
        r"borrow money to buy",
    ]

    @classmethod
    def sanitize(cls, text: str) -> str:
        result = text
        for pattern in cls.banned_patterns:
            result = re.sub(pattern, "[removed]", result, flags=re.IGNORECASE)
        if "not financial advice" not in result.lower():
            result += "\n\nDisclaimer: This is for educational purposes only and not financial advice."
        return result
