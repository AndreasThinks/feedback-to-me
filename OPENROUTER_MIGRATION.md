# OpenRouter Migration Guide

This document explains the changes made to migrate from Google Gemini (direct SDK) to OpenRouter.

## Changes Summary

### 1. Dependencies (`pyproject.toml`)
**Removed:**
- `google-generativeai>=0.8.4`
- `langchain-google-genai>=2.0.9`
- `google-genai>=1.1.0`

**Added:**
- `langchain-openai>=0.2.14`
- `openai>=1.59.6`

### 2. Configuration (`config.py`)
**Removed:**
- `GEMINI_API_KEY`

**Added:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `LLM_MODEL_FAST` - Model for theme extraction (default: `google/gemini-2.0-flash-001`)
- `LLM_MODEL_REASONING` - Model for report generation (default: `google/gemini-2.0-flash-thinking-exp`)
- `LLM_MODEL_FAST_FALLBACK` - Fallback for fast model (default: `anthropic/claude-3-5-haiku-latest`)
- `LLM_MODEL_REASONING_FALLBACK` - Fallback for reasoning model (default: `anthropic/claude-sonnet-4-20250514`)

### 3. LLM Functions (`llm_functions.py`)
**Complete rewrite using OpenRouter:**
- Replaced `ChatGoogleGenerativeAI` with `ChatOpenAI` configured for OpenRouter
- Removed direct `google.genai.Client` usage
- Added automatic fallback logic for all LLM operations
- Improved error handling and logging

## Setup Instructions

### Step 1: Install New Dependencies
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r pyproject.toml
```

### Step 2: Update Your `.env` File
1. Get an OpenRouter API key from https://openrouter.ai/
2. Update your `.env` file:

```bash
# Required: Replace with your OpenRouter key
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional: Customize models (defaults shown)
LLM_MODEL_FAST=google/gemini-2.0-flash-001
LLM_MODEL_REASONING=google/gemini-2.0-flash-thinking-exp

# Optional: Customize fallback models
LLM_MODEL_FAST_FALLBACK=anthropic/claude-3-5-haiku-latest
LLM_MODEL_REASONING_FALLBACK=anthropic/claude-sonnet-4-20250514
```

## Features

### Automatic Fallback System
The new implementation automatically falls back to alternative models if the primary model fails:

1. **Theme Extraction & Anonymization**: 
   - Primary: `LLM_MODEL_FAST` (default: Gemini Flash)
   - Fallback: `LLM_MODEL_FAST_FALLBACK` (default: Claude Haiku)

2. **Report Generation**:
   - Primary: `LLM_MODEL_REASONING` (default: Gemini Thinking)
   - Fallback: `LLM_MODEL_REASONING_FALLBACK` (default: Claude Sonnet)

### Benefits of OpenRouter
- **Multiple Providers**: Access to Google, Anthropic, OpenAI, and more through one API
- **Better Reliability**: Automatic fallbacks prevent service disruptions
- **Cost Optimization**: Switch models based on your needs
- **Easier Testing**: Compare different models without changing code

## Available Models

### Fast Models (for theme extraction)
- `google/gemini-2.0-flash-001` - Google's fast model
- `google/gemini-1.5-flash` - Previous generation
- `anthropic/claude-3-5-haiku-latest` - Anthropic's fast model
- `openai/gpt-4o-mini` - OpenAI's efficient model

### Reasoning Models (for report generation)
- `google/gemini-2.0-flash-thinking-exp` - Google's reasoning model
- `anthropic/claude-sonnet-4-20250514` - Anthropic's balanced model
- `anthropic/claude-opus-4-20250514` - Anthropic's most capable model
- `openai/o1` - OpenAI's reasoning model

See https://openrouter.ai/models for the complete list.

## Testing

After setup, test the migration:

```bash
# Start your application
python main.py

# Test feedback submission and report generation
# Check logs for which models are being used
```

## Troubleshooting

### "Invalid API key" error
- Verify `OPENROUTER_API_KEY` is set correctly in `.env`
- Ensure the key starts with `sk-or-v1-`

### Model not found
- Check model names at https://openrouter.ai/models
- Some models may have changed names or been deprecated

### Fallback not working
- Check logs to see detailed error messages
- Verify fallback model names are correct
- Ensure you have credits for both models

## Rollback (if needed)

If you need to rollback to Google Gemini:
1. Checkout the previous version: `git checkout HEAD~1 llm_functions.py config.py pyproject.toml .env.example`
2. Run `uv sync` or `pip install -r requirements.txt`
3. Restore your `GEMINI_API_KEY` in `.env`

## Support

For issues with:
- **OpenRouter**: https://openrouter.ai/docs
- **This migration**: Check application logs and GitHub issues
