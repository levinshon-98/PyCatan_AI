# Quick Start - API Key Setup

## 🚀 Fast Setup (2 minutes)

### 1. Copy the template:
```bash
copy .env.example .env
```

### 2. Get your Gemini API key:
- Go to: https://aistudio.google.com/app/apikey
- Click "Create API Key"
- Copy the key

### 3. Edit `.env` file and paste your key:
```
GEMINI_API_KEY=AIzaSyC_paste_your_key_here
```

### 4. Test it works:
```bash
python examples/test_ai_config.py
```

## 📚 Full Documentation
See [docs/AI_SETUP.md](docs/AI_SETUP.md) for complete setup guide.

## ✅ Security
- `.env` is NOT committed to Git (safe!)
- Only `.env.example` (template) is in Git
- Your API keys stay on your machine only
