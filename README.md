# osint-claim-verification

Open-source OSINT agent that verifies claims about companies and people.

Give it a claim, a name, or a document (PDF, scan, Word, e-mail). It searches the web and public records,
weighs sources by reliability and independence, and writes a graded report. Confidence is computed from the
evidence, not from what the model says.

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env    # add NVIDIA_API_KEY and TAVILY_API_KEY
python -m osint_harness investigate "Do Kwon is in custody in Montenegro" --as-of 2026-10-13
```

## More

- [docs/usage.md](docs/usage.md) setup, options, benchmark
- [REPORT.md](REPORT.md) design and results
- [docs/architecture.md](docs/architecture.md) diagram

## Tests

```bash
pytest
```
