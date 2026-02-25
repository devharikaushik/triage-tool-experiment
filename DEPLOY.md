# Med-Dev-Vi Deployment and Secret Safety

## 1. Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Never commit secrets

- Keep real keys only in `.env` (local) and Render Environment Variables (production).
- `.env`, local DB files, and virtualenv are ignored by `.gitignore`.
- If a key is ever committed, rotate it immediately.

## 3. Pre-push quick checks

```bash
git status
git diff --cached
rg -n --hidden --glob '!.git/**' --glob '!.venv/**' 'sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35}' .
```

## 4. Deploy with Render Blueprint

1. Push this repo to GitHub.
2. In Render: `New +` -> `Blueprint`.
3. Pick your repo; Render reads `render.yaml`.
4. Deploy.

`render.yaml` already configures:
- `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- persistent disk at `/var/data`
- `DATABASE_URL=sqlite:////var/data/med_dev_vi.db`

## 5. Set production secrets in Render

In Render service -> `Environment`, add keys (when needed):
- `LLM_API_KEY=...`

Do not place production secrets in code, `.env.example`, or GitHub.
