# Hugging Face Spaces deployment

This repo can run as a Docker-based Hugging Face Space.

## What is public

- Replay/session files under `examples/ai_testing/my_games/` can be committed intentionally.
- New sessions created while the Space is running are visible through the app, but free Spaces disk is not persistent across restarts.
- API keys entered in the browser are stored only in the running Python process environment and must not be written to logs.

## What must stay private

- Do not commit `.env`.
- Do not commit real API keys in config files, docs, prompts, responses, or session metadata.
- `.dockerignore` also excludes local `.env`, private YAML config files, virtualenvs, logs, and TTS caches from the Docker image.
- Before pushing, run:

```powershell
python scripts/check_no_secrets.py
```

## Create the Space

1. Create a new Space on Hugging Face.
2. Choose `Docker` as the Space SDK.
3. Push this repo to the Space remote.

The container runs:

```bash
python hf_space_entrypoint.py
```

The entrypoint binds the setup/game server to the `PORT` supplied by Spaces, defaulting to `7860`.

Routes before a game starts:

- `/` public single-page app with `New game` and `Replay library`.
- `/api/sessions` public replay sessions selected by the admin manifest.
- `/api/admin/sessions` session availability list for the in-page admin panel.
- `/healthz` lightweight health check.

## Optional CLI deploy

After logging in locally:

```powershell
pip install -U "huggingface_hub[cli]"
& "$env:APPDATA\Python\Python314\Scripts\hf.exe" auth login
```

Create a Docker Space and set the `hf` git remote:

```powershell
python scripts/deploy_hf_space.py <your-user>/PyCatan-AI
```

Then push:

```powershell
git push hf HEAD:main
```

Or do both in one step:

```powershell
python scripts/deploy_hf_space.py <your-user>/PyCatan-AI --push
```

## Runtime notes

- Users can watch/analyse public replay sessions without an OpenRouter key.
- Starting a live AI game asks for OpenRouter and Gemini keys in the browser.
- The Space entrypoint runs `play_public_entry.py`; when both `OPENROUTER_API_KEY` and `GEMINI_API_KEY` are configured as Space secrets, it adds `--use-env-keys` and the browser skips the API-key step.
- Replay visibility is controlled by `examples/ai_testing/public_sessions.json`; the temporary admin unlock password in the client UI is `20209`.
- The unified AI Analysis tab now reads `/api/current` from the same server, so the deployment does not need a second `5001` web viewer process.
