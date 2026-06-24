# Security Policy — Hermes SEO v3

## Credential Management

- API keys are stored exclusively in `.env` (local) or Streamlit Secrets (cloud).
- The `.env` file is in `.gitignore` and never committed.
- `hermes.config` uses lazy resolution — keys are evaluated at access time, not at import.
- Credentials are **never** logged, never included in HTML/JSON reports, never written to SQLite databases.

## API Request Security

- All external API calls use HTTPS.
- GSC uses OAuth 2.0 with refresh tokens (no long-lived access tokens).
- DataForSEO uses Basic Auth over HTTPS.
- API keys are validated at connector initialization, not stored in session state.

## Input Sanitization

- `hermes.core.guard` provides:
  - `sanitize_input()` — strips control characters, limits length
  - `validate_keyword()` — validates keyword input
  - `validate_url()` — validates and normalizes URLs
- All user inputs are sanitized before processing.
- SQLite uses parameterized queries exclusively (no string concatenation).

## Rate Limiting

- P7 M00 enforces `max_actions_per_day` (default: 20).
- P3 respects `robots.txt` via `protego`.
- P3 enforces `rate_limit_rps` (default: 2 requests/second).
- API connectors use adaptive timeouts and exponential backoff.

## Defensive Only

- P3 (Audit Technique) performs **defensive analysis only** — no penetration testing, no vulnerability scanning.
- Security header analysis (T11) checks for HSTS/CSP/X-Frame presence, does not exploit missing headers.
- P6 (Backlinks) identifies toxic domains but does not perform automated takedown.

## Data Privacy

- P8 (Learning Engine):
  - **Opt-in required** for global model contribution.
  - All data contributed to the global model is anonymized.
  - Client-specific data never leaves the client instance.
  - Users can disable data contribution at any time.
- No user data is sold, shared, or used for purposes other than model improvement.

## Report a Vulnerability

To report a security issue, please email: f.carriere0@gmail.com

Please do not open public issues for security vulnerabilities.

## Dependency Security

- Python dependencies are pinned in `requirements.txt`.
- Dependencies are audited regularly via `pip-audit`.
- System dependencies in Docker are minimal (`python:3.12-slim`).

## Compliance

- Disclaimer system covers: performance projections, data sources, AI-generated content, YMYL, competitive analysis, budget estimates, non-substitution.
- YMYL content requires human expert review before publication (ST09 + M11).
- GDPR: No personal data is collected. All analytics are aggregated and anonymized.
