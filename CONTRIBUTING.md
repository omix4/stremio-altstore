# Contributing

Contributions are welcome! This guide explains how to help.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [How can I help?](#how-can-i-help)
- [Filing an issue](#filing-an-issue)
- [Submitting a pull request](#submitting-a-pull-request)
- [Development setup](#development-setup)
- [Testing](#testing)
- [Style guide](#style-guide)

## Code of conduct

This project and its participants are governed by the [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating you agree to abide by its terms.

## How can I help?

- 🆕 **Reporting new versions** — open an Issue or PR if the updater missed one
- 🐛 **Bug fixes** — particularly parse errors or edge cases
- 📚 **Documentation** — README translations, clarifications, examples
- 🧪 **Testing** — compatibility with different signing apps
- 🆕 **Adding new signing app support** — if a signing app has trouble parsing our JSON, file an Issue with the parsing error message
- 💡 **Feature ideas** — open an Issue to start a discussion
- 🔍 **Code review** — review open PRs

Good first issues are tagged [`good first issue`](https://github.com/omix4/stremio-altstore/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## Filing an issue

Before opening an issue:

1. Search — a similar issue may already exist
2. Read the [README](README.md)
3. Check the [FAQ](#faq) below

When opening a new issue, pick the appropriate template:

| Template | When to use |
|---|---|
| **Bug Report** | Something broke or behaves incorrectly |
| **Feature Request** | New feature or improvement suggestion |
| **Source broken / version missing** | An IPA link is dead or a new version is missing |
| **Question** | General question or help request |

## Submitting a pull request

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/new-thing`)
3. Make your changes
4. Add tests if applicable
5. Follow the [style guide](#style-guide)
6. Commit (`git commit -m 'feat: add new thing'`)
7. Push (`git push origin feat/new-thing`)
8. Open a PR and reference any related issue (`Fixes #123`)

A good PR includes:

- A clear explanation of what and why
- Screenshots (for UI changes)
- Migration notes for breaking changes
- `stremio-updater.py --dry-run` output (for JSON changes)

## Development setup

```bash
# Clone the repo
git clone https://github.com/omix4/stremio-altstore.git
cd stremio-altstore

# Virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dev dependencies (optional; project itself uses stdlib only)
pip install -r requirements-dev.txt

# Code quality
make lint
make format
```

## Testing

The project has standard-library unit tests. Run them together with source validation:

```bash
# Check what the updater would change
make dry-run

# Run a real update
make update

# Verify new IPAs against their Info.plists
make verify

# Run unit tests and validate both static sources
make test
make validate
```

If you add new features, please add unit tests under a new `tests/` directory.

## Style guide

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints (`from __future__ import annotations` is already in use)
- Google or NumPy-style docstrings
- Public functions must have a docstring
- Prefer stdlib (we don't want third-party dependencies)
- Maximum line length: 100 characters
- Strings: double quotes (`"`)
- Boolean checks: `if x is None:` (not `if x == None:`)

### JSON

- 2-space indent
- UTF-8 encoding
- Trailing newline
- Field order: `name`, `identifier`, `subtitle`, `description`, `iconURL`, ...

### Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: new feature
fix: bug fix
docs: documentation only
style: formatting/lint (no logic change)
refactor: code restructuring
test: add or fix tests
chore: maintenance (build, CI, etc.)
```

Examples:

```
feat(updater): add Info.plist parsing for new IPAs
fix(json): correct tvOS bundle ID conflict
docs: update README with new signing app support notes
chore: bump version to 1.1.0
```

## FAQ

**Q: Why two separate JSON files?**
A: Stremio uses `com.stremio.pal` as the bundle ID on both iOS and tvOS. Most signing apps do not allow two apps with the same `bundleIdentifier` inside one source.

**Q: Which signing apps are supported?**
A: Any app that consumes the standard AltStore source format works — Feather, AltStore Classic, AltStore PAL, ESign, Scarlet, Sideloadly, and others. See the [README's compatible signing apps section](README.md#compatible-signing-apps).

**Q: A new Stremio version is out — why didn't the updater catch it?**
A: The updater only scans the last known build + 7 build range. If Stremio jumped a major version (e.g. 2.0.2 → 3.0.0) it might miss it. Open an Issue.

**Q: The updater makes parallel HEAD requests — does Stremio rate-limit?**
A: 16 workers. No rate-limit observed so far, but you can lower `max_workers` inside `stremio-updater.py` if needed.

**Q: I don't want to fork — can I host this myself?**
A: Yes! Put `stremio-ios.json` and `stremio-tvos.json` anywhere you want (S3, Cloudflare Pages, your own server). The only requirements are HTTPS, CORS open, and `Content-Type: application/json`.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
