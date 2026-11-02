# Contributing

Thanks for helping. This is a small project with a simple flow: one issue, one branch, one pull request.

## Set up

Python 3.12 and Node 22. [uv](https://docs.astral.sh/uv/) is the quickest way to get the right Python:

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements-dev.txt
cp .env.example .env            # Ollama works out of the box; see the comments for Gemini
docker compose up -d redis      # Redis on host port 6380, never 6379
cd web && npm ci && cd ..
```

Run it with `uvicorn app.main:app --reload` and `python -m app.worker` (or `EMBED_WORKER=1` for one process), plus `npm run dev` in `web/`. [docs/project_execution.md](docs/project_execution.md) has the full guide, Windows/PowerShell commands, and a troubleshooting table.

## Before you push

```bash
ruff check .
pytest -q
cd web && npm run build
```

The tests are offline: no network, no LLM, no real Redis or database. Keep them that way: mock providers and HTTP, as the existing tests do.

## Workflow

1. **Issue first.** Use a template; say what "done" means.
2. **Branch** from `main`: `<type>/<issue#>-<slug>`, e.g. `fix/27-fetch-cache-key`.
3. **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, with a scope when it helps (`fix(fetch): ...`).
4. **Pull request** with the template filled in and `Closes #N`. CI must be green (`lint-and-test`, `web`, `compose-build`, `attribution-guard`).
5. **Squash merge.** The PR title becomes the commit on `main`, so write it as a Conventional Commit. The branch is deleted automatically.

`main` is protected: no direct pushes, no force-pushes, linear history.

## Attribution

Commits, pull requests, issues and merge messages carry the human author only. Don't add AI co-author trailers, "generated with" footers, or tool tags; a CI check rejects them. Mentions of AI providers as **product** content (Gemini, Anthropic, OpenAI as LLM backends) are fine.

## Security

Never commit keys, tokens or `.env` files. Report vulnerabilities privately: see [SECURITY.md](SECURITY.md).
