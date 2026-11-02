# Security policy

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub: **Security → Report a vulnerability** on this repository. Don't open a public issue.

Include what you found, how to reproduce it, and the impact you expect. You'll get an acknowledgement within 3 days and a status update within 7 days. Fixes ship as soon as they're ready, with credit in the release notes if you'd like it.

## Supported versions

Only the latest release on `main` (the live deployment) receives fixes.

## Scope

In scope:
- the API (`app/`): authentication (API keys, Supabase JWTs), quotas and rate limits, the document fetcher's SSRF guard, BYOK key handling
- the web app (`web/`)
- the deployment configuration in this repository

Out of scope: third-party services the app depends on (Supabase, Upstash, LLM providers, screener.in), denial of service through volume alone, and findings that need a compromised account or machine.

## Handling secrets

API keys are stored only as SHA-256 hashes and shown once. Bring-your-own provider keys travel through a short-lived Redis side channel, never through the job queue or logs. If you find a way to read either, that's a vulnerability worth reporting.
