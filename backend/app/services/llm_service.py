import json
from app.config import settings

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class LLMService:
    @staticmethod
    def build_prompt(context: dict, message: str) -> str:
        return f"""
You are an AI stock assistant for educational use only.
Never promise gains. Never say guaranteed profit. Never instruct the user to go all in.
Be concise, practical, and explain the reasoning.

User context:
{json.dumps(context, indent=2)}

User question:
{message}

Format:
1. Summary
2. Suggested action
3. Why
4. Risks
5. Alternatives
6. Disclaimer
""".strip()

    @staticmethod
    def generate(prompt: str) -> str:
        if not settings.OPENAI_API_KEY or OpenAI is None:
            return (
                "1. Summary: Your portfolio looks moderately concentrated.\n"
                "2. Suggested action: Consider holding core positions and using watchlist alerts for pullbacks instead of rushing into new buys.\n"
                "3. Why: This reduces impulsive decisions and fits a more measured retail workflow.\n"
                "4. Risks: Broad market weakness, earnings surprises, and sector concentration can still hurt performance.\n"
                "5. Alternatives: Buy in small tranches, wait for confirmation, or set alerts around support levels.\n"
                "6. Disclaimer: This is for educational purposes only and not financial advice."
            )

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt,
        )
        return response.output_text
