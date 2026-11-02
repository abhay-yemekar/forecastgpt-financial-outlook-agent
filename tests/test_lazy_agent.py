import os
import subprocess
import sys
from pathlib import Path

from app.agent import ForecastAgent
from app.config import settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_api_imports_without_an_llm_key(tmp_path):
    """The API only enqueues; it must boot even when the operator has no
    chat-model key (BYOK-only deployments, misconfigured env)."""
    env = {
        **os.environ,
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "",
        "EMBED_WORKER": "0",
        "MODEL_SELF_TEST": "0",
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'boot.db').as_posix()}",
        "DATA_DIR": str(tmp_path / "data"),
    }
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_byok_job_works_without_operator_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    agent = ForecastAgent()  # must not need the operator key
    model = agent._chat_model("sk-user-own-key")
    assert model is not None
    assert agent.llm is None  # the operator model was never built
