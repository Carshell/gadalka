# gadalka

# Longchain / Gadalka (Telegram bot)

This repository contains a Telegram bot (flat file layout) built with **python-telegram-bot** + **LangChain/LangGraph**.

## Prerequisites

- Python **3.10+** (recommended 3.11)
- A Telegram bot token from **@BotFather**
- An OpenAI API key

## Clone from GitHub

```bash
git clone https://github.com/Carshell/gadalka.git
cd gadalka
```

## Setup (Windows / PowerShell)

From the repo root:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment variables

Create your local `.env` 

```bash
copy .env.example .env
```

Then edit `.env` and set:

- `OPENAI_API_KEY`
- `BOT_API`

Optional:

- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `TARO_URL` 
- `NUMEROLOGY_URL`
- `URL_TIMEOUT_SECONDS` (default: `15`)

## Run the bot

```bash
python main.py
```

You should see:

- `🤖 Bot is running...`

Then open Telegram and send `/start` to your bot.

## Notes

- SQLite database file is created automatically: `users.db`
- If you change `.env`, restart the bot.

