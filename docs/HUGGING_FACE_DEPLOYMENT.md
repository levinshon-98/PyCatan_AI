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

The entrypoint binds the standalone replay viewer to the `PORT` supplied by Spaces, defaulting to `7860`.

Important routes:

- `/` public replay viewer.
- `/api/sessions` public replay sessions selected by the admin manifest.
- `/api/admin/sessions` session availability list for the in-page admin panel.
- `/api/mobile_link_request` stores mobile email requests and sends a desktop link when email is configured.
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
- The Space entrypoint only serves replay sessions. It does not start a new live game.
- Replay visibility is controlled by `examples/ai_testing/my_games/replay_public_sessions.json` unless `REPLAY_VIEWER_PUBLIC_CONFIG` points somewhere else.
- Hugging Face runs with `REPLAY_VIEWER_REQUIRE_PUBLIC_CONFIG=1`, so no sessions are public until they are selected in the public config.
- The temporary admin unlock password in the client UI is `catan-replay`.
- For persistent admin edits on Hugging Face, either commit `replay_public_sessions.json` or enable Space persistent storage and set `REPLAY_VIEWER_PUBLIC_CONFIG=/data/replay_public_sessions.json`.
- Mobile email sending can use EmailJS. See `docs/mobile_link_emailjs.md`.
