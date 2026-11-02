"""Startup model self-test: one tiny chat call and one embedding call.

Providers retire models on a schedule (gemini-2.0-flash-lite and
text-embedding-004 both went away), and the pipeline treats transcript RAG
as best-effort, so a dead model otherwise surfaces only as failed or
quietly thinner reports. Running this when a worker starts turns that into
one loud log line, and GET /ready reports the result.
"""

import threading

from app.ai.factory import get_embedding_provider, get_llm_provider
from app.config import settings
from app.utils.logger import get_logger

log = get_logger("ai.selftest")

# "unchecked" until a self-test runs in this process; then "ok" or
# "failed (<ErrorClass>)". Only the class name is kept here because /ready
# is public; the full error goes to the log.
status: dict[str, str] = {"chat": "unchecked", "embeddings": "unchecked"}


def _check(kind: str, label: str, call) -> None:
    try:
        call()
        status[kind] = "ok"
        log.info(f"Model self-test passed: {kind} model {label}.")
    except Exception as e:
        status[kind] = f"failed ({type(e).__name__})"
        log.error(
            f"MODEL SELF-TEST FAILED: {kind} model {label} is not usable: {e}. "
            "Forecasts will fail or lose transcript analysis until the model env is fixed "
            "(docs/DEPLOY.md D-16)."
        )


def run_model_self_test() -> dict[str, str]:
    """Call the configured chat and embedding models once each."""
    chat_label = f"{settings.LLM_PROVIDER}:{settings.LLM_MODEL}"
    emb_label = f"{settings.EMBEDDING_PROVIDER}:{settings.EMBEDDING_MODEL}"
    _check(
        "chat",
        chat_label,
        lambda: get_llm_provider()
        .get_chat_model(temperature=0)
        .invoke([{"role": "user", "content": "Reply with the single word OK."}]),
    )
    _check(
        "embeddings",
        emb_label,
        lambda: get_embedding_provider().get_embedding_model().embed_query("model self-test"),
    )
    return dict(status)


def start_model_self_test() -> None:
    """Run the self-test in a background thread (never delays startup).
    Disabled with MODEL_SELF_TEST=0."""
    if not settings.MODEL_SELF_TEST:
        return
    threading.Thread(target=run_model_self_test, name="model-self-test", daemon=True).start()
