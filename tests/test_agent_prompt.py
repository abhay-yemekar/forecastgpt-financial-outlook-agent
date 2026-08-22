from app.agent import SYSTEM_PROMPT_TEMPLATE, build_system_prompt


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
