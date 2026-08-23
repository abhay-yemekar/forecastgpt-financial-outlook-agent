import json
import re
from typing import Any

from app.ai.factory import get_llm_provider
from app.config import settings
from app.tools.financial_extractor import extract_financial_metrics
from app.tools.market_data import fetch_stock_price
from app.tools.qualitative_rag import QualitativeAnalysisTool
from app.utils.logger import get_logger

log = get_logger("ForecastAgent")

# ---------------------------------------------------------------------------
# System prompt – keeps role, schema and behaviour very explicit so the model
# produces strong, concrete outputs instead of "unclear".
# The subject company is injected via the {company_name} placeholder, so the
# reasoning rules stay identical for every company.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """
You are ForecastGPT, a financial forecasting agent for {company_name}.

Your goal:
Given structured financial metrics, key transcript snippets and optional market context,
you must produce a concise, investor-style qualitative outlook for the *next quarter*.

Ground rules (very important):
- Use ONLY facts that can be reasonably inferred from the provided inputs.
- If a specific metric is missing, do NOT hallucinate an exact number.
- Instead, speak in directions and trends: "increasing", "declining", "stable", "volatile", etc.
- Always fill the JSON schema fields with your best good-faith view.
- Be specific and differentiated across revenue, profit and margin – avoid saying "unclear" unless there is genuinely no signal.

Output format:
- You MUST return a single JSON object.
- The JSON MUST strictly follow this schema and key order:

{
  "company": "{company_name}",
  "period_analyzed": ["string"],
  "financial_trends": {
     "revenue": "string",
     "net_profit": "string",
     "operating_margin": "string"
  },
  "management_themes": ["string"],
  "risks": ["string"],
  "opportunities": ["string"],
  "qualitative_forecast_next_quarter": "string",
  "confidence": {
     "level": "low|medium|high",
     "reasons": ["string"]
  }
}

Field guidance:
- period_analyzed: list of the quarter names or periods you are basing your view on.
- financial_trends.revenue: direction + 1 short reason (e.g. "increasing, driven by strong BFSI demand").
- financial_trends.net_profit: direction + key drivers (e.g. "stable despite wage hikes due to cost optimisation").
- financial_trends.operating_margin: direction + colour on utilisation / pricing / costs.
- management_themes: 4–8 short bullets summarising what management emphasised.
- risks: 3–6 concise, real risks (macro, client concentration, pricing pressure, attrition, etc.).
- opportunities: 3–6 concise upside levers (GenAI deals, cost takeout programmes, large deal pipeline, etc.).
- qualitative_forecast_next_quarter: 2–4 sentences summarising your expectation for the next quarter.
- confidence: honest assessment based on depth/clarity of evidence. If transcripts and multiple quarters
  of data are available, confidence should usually be "medium" or "high".

Do NOT:
- Add keys outside this schema.
- Wrap the JSON in markdown or natural language.
- Leave fields empty; if something is genuinely unknown, say that explicitly in the string.
"""


def build_system_prompt(company_name: str) -> str:
    # .replace (not str.format) so the literal JSON braces in the schema survive.
    return SYSTEM_PROMPT_TEMPLATE.replace("{company_name}", company_name)


# ---------------------------------------------------------------------------
# Helper: robust JSON extraction
# ---------------------------------------------------------------------------

def _parse_json_loose(text: str) -> dict[str, Any]:
    """
    Try to recover a JSON object from an LLM response.
    Handles:
    - pure JSON
    - JSON with leading/trailing text
    - JSON wrapped in markdown fences
    """
    text = text.strip()

    # Strip ```json fences if present
    fence_match = re.search(r"```(?:json)?(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: first {...} block
    brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if brace_match:
        json_str = brace_match.group(0)
        return json.loads(json_str)

    raise ValueError("Could not find valid JSON in model output")


# ---------------------------------------------------------------------------
# Helper: compress transcript themes so the prompt fits within context window
# ---------------------------------------------------------------------------

def _compress_themes(themes: Any,
                     max_snippets_per_topic: int = 2,
                     max_chars_per_snippet: int = 400) -> Any:
    """
    themes is usually a dict[str, list[str]] from QualitativeAnalysisTool.
    We keep only the first `max_snippets_per_topic` snippets per topic and
    truncate each snippet to `max_chars_per_snippet` characters to avoid
    blowing up the LLM context window.
    """
    if not isinstance(themes, dict):
        return themes

    compressed: dict[str, list[str]] = {}
    for topic, snippets in themes.items():
        if not isinstance(snippets, list):
            continue
        trimmed: list[str] = []
        for snip in snippets[:max_snippets_per_topic]:
            if not isinstance(snip, str):
                continue
            trimmed.append(snip[:max_chars_per_snippet])
        if trimmed:
            compressed[topic] = trimmed
    return compressed


MAX_PROMPT_CHARS = 10000  # safeguard for very large inputs


class ForecastAgent:
    def __init__(self) -> None:
        self.llm = get_llm_provider().get_chat_model(temperature=0.2)
        log.info(f"ForecastAgent initialised with LLM_PROVIDER={settings.LLM_PROVIDER} model: {settings.LLM_MODEL}")

    def run(
        self,
        query: str,
        financial_pdfs: list[str],
        transcripts: list[str],
        company_name: str,
        symbol: str,
    ) -> dict[str, Any]:
        # 1) Extract hard financial metrics from quarterly PDFs
        fin = extract_financial_metrics(financial_pdfs)

        # 2) Build RAG index over transcripts – but keep failure completely non-fatal
        themes: Any = []
        try:
            if transcripts:
                rag = QualitativeAnalysisTool()
                rag.build_index(transcripts)
                raw_themes = rag.query_themes(
                    [
                        "revenue growth drivers and headwinds",
                        "margin outlook and cost pressures",
                        "deal pipeline and demand commentary",
                        "AI and GenAI opportunities and use-cases",
                        "client spend behaviour and macro commentary",
                        "key risks highlighted by management",
                    ]
                )
                themes = _compress_themes(raw_themes)
            else:
                themes = ["No transcript provided by user."]
        except Exception as e:
            log.warning(f"Transcript RAG failed: {e}")
            themes = ["Transcript analysis failed; proceeding with financials only."]

        # 3) Optional market data – completely best-effort
        try:
            market = fetch_stock_price(symbol)
        except Exception as e:  # pragma: no cover
            log.warning(f"Market fetch failed, continuing without it: {e}")
            market = {}

        # 4) Build a single user prompt string (no templating logic that can break)
        user_parts = [
            f"Task: {query}",
            "",
            "Structured financial metrics extracted from quarterly financial statements (already parsed for you):",
            json.dumps(fin, indent=2, ensure_ascii=False),
            "",
            "Key management commentary snippets from earnings call transcripts, grouped by analytical theme:",
            json.dumps(themes, indent=2, ensure_ascii=False),
            "",
            f"Optional market context for the {company_name} stock (can be empty):",
            json.dumps(market, indent=2, ensure_ascii=False),
            "",
            "Now, using ONLY the information above and following the schema from the system prompt, "
            "produce the final JSON forecast object.",
        ]
        user_prompt = "\n".join(user_parts)

        # Final character-level safeguard
        if len(user_prompt) > MAX_PROMPT_CHARS:
            # keep the tail – it will always contain the most recent, structured pieces
            user_prompt = user_prompt[-MAX_PROMPT_CHARS:]

        messages = [
            {"role": "system", "content": build_system_prompt(company_name)},
            {"role": "user", "content": user_prompt},
        ]

        raw = self.llm.invoke(messages).content

        # 5) Parse / normalise JSON with robust error-handling
        try:
            parsed = _parse_json_loose(raw)
        except Exception as e:
            log.error(f"Model output was not valid JSON: {e}")
            # Minimal but still useful fallback payload
            return {
                "company": company_name,
                "period_analyzed": [],
                "financial_trends": {
                    "revenue": "unclear",
                    "net_profit": "unclear",
                    "operating_margin": "unclear",
                },
                "management_themes": themes if themes else [],
                "risks": ["Model output invalid JSON"],
                "opportunities": [],
                "qualitative_forecast_next_quarter": "",
                "confidence": {
                    "level": "low",
                    "reasons": ["Invalid JSON from model"],
                },
                "sources": {
                    "financial_docs": financial_pdfs,
                    "transcripts": transcripts,
                },
                "market_context": market,
                "financial_metrics": fin,
            }

        # 6) Ensure all expected keys exist so the frontend / demo never breaks
        parsed.setdefault("company", company_name)
        parsed.setdefault("period_analyzed", [])
        parsed.setdefault(
            "financial_trends",
            {
                "revenue": "unclear",
                "net_profit": "unclear",
                "operating_margin": "unclear",
            },
        )
        parsed.setdefault("management_themes", [])
        parsed.setdefault("risks", [])
        parsed.setdefault("opportunities", [])
        parsed.setdefault("qualitative_forecast_next_quarter", "")
        parsed.setdefault(
            "confidence",
            {
                "level": "low",
                "reasons": ["Missing confidence from model"],
            },
        )

        parsed["sources"] = {
            "financial_docs": financial_pdfs,
            "transcripts": transcripts,
        }
        parsed["market_context"] = market
        # Raw extractor output (numeric metrics + trend_summary) so clients
        # can chart the data the forecast was grounded on.
        parsed["financial_metrics"] = fin

        return parsed
