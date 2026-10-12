# Security Policy

## Supported versions

Only the latest code on `main` is supported.

## Reporting a vulnerability

**Please don't open a public issue.** Use the repo's **Security** tab → **Report a vulnerability**, or contact [@swapnilchaudhari007](https://github.com/swapnilchaudhari007).

Include a description, the impact, steps to reproduce and any suggested fix. You'll get an acknowledgement within 72 hours and an initial assessment within 7 days. Reporters are credited unless they'd rather stay anonymous.

## What we especially care about in SocietyMitra

- **Resident data:** names, flat numbers, phone numbers or dues leaking through answers or logs
- **Prompt injection:** notices, documents or search results that steer the agent
- **Wrong legal guidance:** answers presented as authoritative on society bye-laws or co-operative law without sources
- **API keys:** Nebius or Tavily keys exposed

## For contributors

- Never commit secrets: use `.env` files (git-ignored) or GitHub Actions secrets
- Keep real personal data out of code, tests, issues and screenshots
- Treat all user input, and anything passed to an AI model, as untrusted
