import json
from app.config import settings

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _contextual_fallback(context: dict, message: str) -> str:
    holdings = context.get("holdings") or []
    market = context.get("market_snapshot") or {}
    news = context.get("news") or {}
    earnings = context.get("earnings") or {}

    top = sorted(
        [h for h in holdings if isinstance(h, dict)],
        key=lambda x: float(x.get("shares", 0) or 0) * float(x.get("market_price", 0) or 0),
        reverse=True,
    )[:3]

    top_lines = []
    for h in top:
        mv = float(h.get("shares", 0) or 0) * float(h.get("market_price", 0) or 0)
        top_lines.append(f"- {h.get('symbol')}: market value ≈ ${mv:,.2f}")

    idx_lines = []
    for i in (market.get("indices") or [])[:3]:
        if not isinstance(i, dict):
            continue
        chg = i.get("change_pct")
        if chg is None:
            idx_lines.append(f"- {i.get('label')}: n/a")
        else:
            idx_lines.append(f"- {i.get('label')}: {float(chg):+.2f}%")

    earnings_lines = []
    for s, e in (earnings or {}).items():
        if not isinstance(e, dict):
            continue
        if e.get("next_earnings"):
            earnings_lines.append(f"- {s}: next earnings {e.get('next_earnings')}")
    earnings_lines = earnings_lines[:5]

    news_lines = []
    for s, arr in (news or {}).items():
        if not isinstance(arr, list) or not arr:
            continue
        n0 = arr[0] if isinstance(arr[0], dict) else {}
        t = n0.get("title")
        if t:
            news_lines.append(f"- {s}: {t}")
    news_lines = news_lines[:5]

    zh = any("\u4e00" <= ch <= "\u9fff" for ch in message)
    if zh:
        return (
            "1) 总结\n"
            "目前是基于你真实持仓+市场快照的快速分析（降级模式，未启用云端大模型）。\n\n"
            "2) 当前持仓重点\n"
            + ("\n".join(top_lines) if top_lines else "- 暂无持仓数据")
            + "\n\n3) 市场环境\n"
            + ("\n".join(idx_lines) if idx_lines else "- 暂无指数数据")
            + "\n\n4) 近期事件（新闻/财报）\n"
            + (("\n".join(earnings_lines + news_lines)) if (earnings_lines or news_lines) else "- 暂无可用事件")
            + "\n\n5) 可执行建议\n"
            "- 对前3大仓位设置分层止损与提醒。\n"
            "- 财报前避免重仓追高，优先小仓位试探。\n"
            "- 若市场波动率上升，先降集中度再考虑加仓。\n\n"
            "6) 说明\n"
            "这是教育用途，不构成投资建议。"
        )

    return (
        "1. Summary\n"
        "Quick portfolio-aware analysis (fallback mode; cloud LLM not active).\n\n"
        "2. Top holdings\n"
        + ("\n".join(top_lines) if top_lines else "- No holdings data")
        + "\n\n3. Market snapshot\n"
        + ("\n".join(idx_lines) if idx_lines else "- No index data")
        + "\n\n4. Upcoming catalysts (news/earnings)\n"
        + (("\n".join(earnings_lines + news_lines)) if (earnings_lines or news_lines) else "- No catalyst data")
        + "\n\n5. Suggested action\n"
        "- Tighten risk controls on top 3 positions.\n"
        "- Avoid oversized adds right before earnings.\n"
        "- If volatility rises, reduce concentration first.\n\n"
        "6. Disclaimer\n"
        "Educational use only, not financial advice."
    )


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
2. Suggested action (Buy/Add/Hold/Trim/Exit candidates)
3. Why (must reference concrete data from context)
4. Risks
5. Alternatives
6. Next 7 days watchlist (events/news/earnings)
7. Disclaimer

Rules:
- No guaranteed returns.
- No all-in recommendations.
- Include evidence bullets like: [DATA] symbol, metric, value.
""".strip()

    @staticmethod
    def generate(prompt: str, context: dict | None = None, message: str = "") -> str:
        if not settings.OPENAI_API_KEY or OpenAI is None:
            return _contextual_fallback(context or {}, message)

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.responses.create(
                model=settings.OPENAI_MODEL,
                input=prompt,
                timeout=20,
            )
            text = (response.output_text or "").strip()
            return text if text else _contextual_fallback(context or {}, message)
        except Exception:
            return _contextual_fallback(context or {}, message)
