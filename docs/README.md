# Documentation

This directory contains the Sphinx documentation for General Pipeline.

## Building Documentation Locally

### Prerequisites

```bash
pip install sphinx sphinx-rtd-theme myst-parser
```

### Build HTML Documentation

```bash
cd docs
make html
```

The generated documentation will be in `build/html/`. Open `build/html/index.html` in your browser.

### Clean Build

```bash
cd docs
make clean
make html
```

## Automated Documentation Deployment

Documentation is automatically built and deployed when changes are pushed to the main branch.

### GitHub Pages

Documentation is automatically deployed to GitHub Pages via GitHub Actions (`.github/workflows/docs.yml`).

Access at: `https://<username>.github.io/<repository>/`

### GitLab Pages

Documentation is automatically deployed to GitLab Pages via GitLab CI (`.gitlab-ci.yml`).

Access at: `https://<username>.gitlab.io/<repository>/`

### Gitea Pages

Documentation can be built via Gitea Actions (`.gitea/workflows/docs.yml`).

Deployment depends on your Gitea instance configuration. Consult your Gitea administrator for enabling Pages.

## Documentation Structure

```
docs/
├── source/
│   ├── conf.py              # Sphinx configuration
│   ├── index.rst            # Main documentation index
│   ├── getting_started.rst  # Getting started guide
│   ├── user_guide.rst       # User guide
│   ├── api_reference.rst    # API reference (auto-generated)
│   ├── migration_guide.md   # OmegaConf migration guide (symlink)
│   └── registration_guide.md # Registration guide (symlink)
├── build/                   # Generated documentation (git-ignored)
└── Makefile                 # Build commands
```

## Adding New Documentation

1. Create a new `.rst` or `.md` file in `docs/source/`
2. Add it to the table of contents in `docs/source/index.rst`
3. Build and test locally
4. Commit and push - documentation will be automatically deployed

## Supported Formats

- **reStructuredText (.rst)**: Native Sphinx format with powerful directives
- **Markdown (.md)**: Supported via myst-parser extension

## Theme

The documentation uses the [Read the Docs theme](https://sphinx-rtd-theme.readthedocs.io/).
