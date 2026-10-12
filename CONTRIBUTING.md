# Contributing to SocietyMitra

Thanks for helping improve **SocietyMitra**, an AI co-secretary for housing societies, built on NVIDIA Nemotron via Nebius Token Factory.

## Ways to contribute

- Report a bug or suggest an idea in [Issues](https://github.com/swapnilchaudhari007/societymitra/issues/new/choose)
- Pick up an issue labelled `good first issue` or `help wanted`
- Improve docs, examples or translations
- Review open pull requests

## Local setup

```bash
git clone https://github.com/<your-username>/societymitra.git
cd societymitra
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Nebius + Tavily keys
python app.py
```

Run the tests before opening a PR:

```bash
pytest
```

## Workflow

1. Fork the repo and create a branch: `git checkout -b feat/short-description`
2. Keep each PR focused on one change
3. Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
4. Open a PR against `main` and fill in the template

## Areas you can work on

- Agent / reasoning
- Knowledge base (bye-laws, notices)
- Web search (Tavily)
- UI
- Docker deployment

## AI-assisted contributions

AI tools are welcome. You are responsible for every line you submit: review it, test it and say in the PR if AI helped.

## Code of conduct

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Please don't report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).
