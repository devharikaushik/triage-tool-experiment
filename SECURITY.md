# Security Notes

This app is configured to reduce accidental secret exposure and basic web risks.

## What is already in place

- `.gitignore` excludes `.env`, local SQLite DB files, and virtualenv artifacts.
- App reads config from environment variables.
- Response security headers are enabled (`CSP`, `X-Frame-Options`, `nosniff`, etc.).
- `TrustedHostMiddleware` is enabled using `ALLOWED_HOSTS`.

## Required operator actions

- Store real API keys only in deployment environment variables (Render dashboard), never in code.
- Set `ALLOWED_HOSTS` in production to your real hostnames.
- Rotate any key immediately if you suspect it was exposed.
- Keep Render service private logs access limited to your team.

## Important reality check

No internet-exposed app can be made "unhackable". The goal is risk reduction:
- secret hygiene
- minimal permissions
- timely key rotation
- controlled access to infrastructure
