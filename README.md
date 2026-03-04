# Claude Code Preflight

A CLI tool that generates a focused briefing of Claude Code best practices before you start a task. Describe what you're about to do, and get back a targeted briefing with the most relevant workflows, configuration tips, and gotchas — ready to paste into your session or CLAUDE.md.

No vector DB. No embeddings. Just the full Claude Code docs corpus + a smart routing prompt.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
# Or create a .env file (see .env.example)

# 3. Run a preflight briefing
python preflight.py "Set up GitHub Actions to auto-review PRs"
```

## Usage

```bash
# Basic usage
python preflight.py "Refactor the auth module to use JWT"

# With environment details
python preflight.py --env "VS Code, Python, macOS" "Debug a memory leak"

# With concerns
python preflight.py --concerns "speed, cost" "Migrate React app to TypeScript"

# Copy briefing to clipboard
python preflight.py -c "Add tests for the payment service"

# Save briefing to file
python preflight.py -f briefing.md "Set up MCP server for Jira"

# Interactive mode (prompts for everything)
python preflight.py --interactive

# Use Opus for deeper analysis
python preflight.py -m claude-opus-4-6 "Architect a new microservice"

# Show token usage and timing
python preflight.py -v "Write a hook that runs ESLint after edits"
```

## How It Works

1. **Corpus**: 58 Claude Code documentation pages stored as clean markdown in `corpus/`
2. **System prompt**: Instructs Claude to extract only practices relevant to your specific task
3. **Prompt caching**: The corpus is cached server-side, so repeated calls are fast and cheap (~$0.05 vs ~$0.21 for the first call)

The full corpus (~166K tokens) is sent as context with every request. Claude reads it, identifies the relevant sections, and returns a structured briefing with:

- **Task Understanding** — restates what you're doing
- **Recommended Workflow** — which mode, tools, and session structure to use
- **Key Best Practices** — numbered, concrete, with actual commands
- **Configuration Checklist** — CLAUDE.md additions, permissions, hooks, plugins
- **Watch Out For** — gotchas and common mistakes
- **Sources** — which doc pages were consulted

## Smart Scope Mode

Instead of writing a one-liner, drop `.md` files describing your project into `scope/` and let the system generate the optimal task description for you.

```bash
# Auto-generate task from scope files, review it, then get briefing
python3 preflight.py --from-scope

# Auto-approve the generated task (skip review step)
python3 preflight.py --from-scope -y

# Use specific files instead of the scope/ directory
python3 preflight.py --from-scope --scope-files docs/overview.md docs/sprint.md

# Use a custom scope directory
python preflight.py --from-scope --scope-dir ./docs/project/

# Combine with other flags
python preflight.py --from-scope -y -c -v
```

### How it works

1. **Pass 1** (Haiku, ~$0.002): Reads your scope files and generates a comprehensive TASK / ENVIRONMENT / CONCERNS description
2. **You review/edit** the generated description (or skip with `-y`)
3. **Pass 2** (Sonnet): Runs the normal preflight briefing with that description

### Scope file examples

Add any `.md` files to `scope/`. Use numeric prefixes to control order:

```text
scope/
├── 01-project-overview.md    # What the project is, goals, current state
├── 02-tech-stack.md          # Languages, frameworks, tooling, infrastructure
├── 03-current-sprint.md      # What you're working on right now
└── 04-conventions.md         # Team norms, linting, PR process
```

No special format required — just plain markdown. The system reads whatever you put there.

## CLI Flags

| Flag | Short | Description |
| ---- | ----- | ----------- |
| `task` | | Task description (positional argument) |
| `--env` | `-e` | Environment: IDE, OS, language/framework |
| `--concerns` | | Key concerns: speed, safety, collaboration |
| `--interactive` | `-i` | Prompts for task/env/concerns step by step |
| `--to-clipboard` | `-c` | Copy briefing to clipboard |
| `--to-file` | `-f` | Save briefing to a file |
| `--model` | `-m` | Override model (e.g., `claude-opus-4-6`) |
| `--verbose` | `-v` | Show token usage and timing |
| `--config` | | Path to config file (default: `config.yaml`) |
| `--from-scope` | `-s` | Generate task from project scope files |
| `--scope-dir` | | Scope directory (default: `./scope/`) |
| `--scope-files` | | Specific scope files to use |
| `--auto-approve` | `-y` | Skip review of generated task |
| `--scope-model` | | Override model for Pass 1 |

## Configuration

Edit `config.yaml` to customize defaults:

```yaml
model: claude-sonnet-4-6       # Sonnet for speed/cost; Opus for depth
corpus_dir: ./corpus
custom_corpus_dir: ./corpus_custom
prompts_dir: ./prompts
max_tokens: 4096
max_doc_chars: 15000           # Per-doc truncation limit
cache_corpus: true

# Smart scope settings
scope_dir: ./scope             # Default scope file directory
scope_model: claude-haiku-4-5-20251001  # Lighter model for Pass 1
scope_max_tokens: 1024         # Max output for task generation
```

## Updating the Corpus

Re-scrape the docs when they change:

```bash
# Preview what would be fetched
python scrape_docs.py --dry-run

# Re-scrape all pages (skips existing files)
python scrape_docs.py

# Force re-scrape everything
python scrape_docs.py --force
```

The scraper fetches the `llms.txt` index from `code.claude.com`, downloads each page as raw markdown, cleans MDX components, and saves with YAML frontmatter.

## Custom Corpus

Add your own notes to `corpus_custom/` — they're included alongside the official docs:

```text
corpus_custom/
├── my-workflow-tips.md       # Things you've learned
├── project-patterns.md       # Patterns for your projects
└── common-mistakes.md        # Mistakes to avoid
```

Custom files can use the same YAML frontmatter format:

```yaml
---
title: "My Workflow Tips"
section: "Custom"
---
```

## Project Structure

```text
├── corpus/                  # 58 scraped doc pages (auto-generated)
├── corpus_custom/           # Your own notes (optional)
├── scope/                   # Project scope files for --from-scope mode
├── prompts/
│   ├── system_prompt.md     # Routing/extraction prompt
│   ├── output_template.md   # Output format definition
│   └── scope_prompt.md      # Pass 1 prompt for task generation
├── preflight.py             # Main CLI script
├── scrape_docs.py           # One-time doc scraper
├── mdx_cleaner.py           # MDX-to-markdown converter
├── config.yaml              # Configuration
├── requirements.txt         # Python dependencies
└── .env.example             # API key template
```

## Cost

With `claude-sonnet-4-6`:

- **First call**: ~$0.21 (corpus cached server-side)
- **Subsequent calls**: ~$0.05 (reads from cache)
- **Output**: ~$0.02 per briefing
- **Scope mode (Pass 1)**: adds ~$0.002 (Haiku)

Use `--verbose` to see exact token counts per call.
