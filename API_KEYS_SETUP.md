# 🔐 API Keys Setup Guide

## ⚠️ IMPORTANT: Never Commit API Keys!

API keys are **sensitive credentials** and should **NEVER** be committed to Git.

## 🚀 Setup Instructions

### Step 1: Create your `.env` file

```bash
# Copy the example file
cp .env.example .env
```

### Step 2: Add your API keys

Edit the `.env` file and add your actual API keys:

```bash
# Google Gemini API Key (get it from: https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_actual_api_key_here

# Add other keys as needed...
```

### Step 3: Verify protection

The `.env` file is already in `.gitignore` and will not be committed:

```bash
# Verify it's ignored
git check-ignore -v .env
# Should output: .gitignore:85:.env      .env
```

## 🔍 How It Works

All scripts now use environment variables:

```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
```

## ✅ Security Checklist

- [x] `.env` file is in `.gitignore`
- [x] API keys loaded from environment variables
- [x] No hardcoded keys in code
- [x] `.env.example` template provided (without actual keys)

## 🛡️ If You Accidentally Committed a Key

If you accidentally committed an API key:

1. **Revoke the key immediately** on the provider's website
2. **Generate a new key**
3. **Remove the key from Git history**:
   ```bash
   # Use git filter-branch or BFG Repo-Cleaner
   # Or simply delete and recreate the repo if it's early stage
   ```
4. **Update your `.env` with the new key**

## 📚 Documentation

- [.env.example](.env.example) - Template with all available environment variables
- [.gitignore](.gitignore) - Protects sensitive files from being committed
