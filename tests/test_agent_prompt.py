import json

from app.agent import (
    MAX_PROMPT_CHARS,
    MAX_QUERY_CHARS,
    SYSTEM_PROMPT_TEMPLATE,
    build_system_prompt,
    build_user_prompt,
)


def test_prompt_is_company_parameterized():
    prompt = build_system_prompt("Infosys")
    assert "Infosys" in prompt
    assert "TCS" not in prompt
    assert "{company_name}" not in prompt  # placeholder fully substituted


def test_template_schema_braces_survive_substitution():
    prompt = build_system_prompt("HDFC Bank")
    # JSON schema braces are literal, not format placeholders.
    assert '"financial_trends"' in prompt
    assert '"confidence"' in prompt
    assert prompt.count("{") == prompt.count("}")


def test_two_companies_get_distinct_prompts():
    assert build_system_prompt("TCS") != build_system_prompt("Wipro")
    # The untouched template still carries the placeholder.
    assert "{company_name}" in SYSTEM_PROMPT_TEMPLATE


# --- user-prompt budget (F6): the task and metrics are never cut ----------

FIN = {
    "documents": [{"path": "data/cache/q2.pdf", "metrics": {"total_revenue_inr_cr": "65,799", "net_profit_inr_cr": "12,075"}}],
    "trend_summary": {"total_revenue_inr_cr": {"direction": "up", "pct_change": 2.3}},
}
CLOSING = "produce the final JSON forecast object."


def _huge_themes(topics=6, snippets=5, chars=2000):
    return {f"topic {t}": [f"snippet {t}.{s} " + "x" * chars for s in range(snippets)] for t in range(topics)}


def test_oversized_themes_shrink_but_task_and_metrics_survive():
    prompt = build_user_prompt("Outlook for next quarter", FIN, _huge_themes(), {"price_inr": 1}, "TCS")
    assert len(prompt) <= MAX_PROMPT_CHARS
    assert prompt.startswith("Task: Outlook for next quarter")
    assert json.dumps(FIN, indent=2, ensure_ascii=False) in prompt
    assert prompt.endswith(CLOSING)
    assert "snippet 0.0" in prompt  # themes were trimmed, not dropped


def test_small_inputs_are_kept_whole():
    themes = {"margin outlook": ["Margins held at 24.5% despite wage hikes."]}
    prompt = build_user_prompt("q", FIN, themes, {}, "TCS")
    assert "Margins held at 24.5% despite wage hikes." in prompt
    assert len(prompt) < MAX_PROMPT_CHARS


def test_overlong_query_is_capped():
    prompt = build_user_prompt("y" * 50_000, FIN, {}, {}, "TCS")
    task_line = prompt.splitlines()[0]
    assert len(task_line) <= len("Task: ") + MAX_QUERY_CHARS + len(" [...]")
    assert len(prompt) <= MAX_PROMPT_CHARS


def test_metrics_are_never_truncated_even_when_they_exceed_the_budget():
    big_fin = {"documents": [{"path": f"doc{i}.pdf", "metrics": {"note": "z" * 500}} for i in range(30)]}
    prompt = build_user_prompt("q", big_fin, _huge_themes(), {}, "TCS")
    assert json.dumps(big_fin, indent=2, ensure_ascii=False) in prompt
    assert "Transcript themes omitted" in prompt
    assert prompt.endswith(CLOSING)
