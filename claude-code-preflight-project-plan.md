# Claude Code Preflight Briefing System — Project Plan

## What We're Building

A CLI tool that, before any Claude Code session, takes a plain-English description of your task and returns a focused briefing of the most relevant Claude Code best practices, workflows, and configuration tips. It works by feeding your task description + the full Claude Code docs corpus into Claude, which extracts and organizes only what's relevant.

No vector DB. No embeddings. Just a well-structured corpus and a smart routing prompt.

---

## Project Structure

```
claude-code-preflight/
├── corpus/                     # All Claude Code docs as markdown files
│   ├── 00-overview.md
│   ├── 01-quickstart.md
│   ├── 02-how-claude-code-works.md
│   ├── 03-common-workflows.md
│   ├── 04-best-practices.md
│   ├── 05-extend-claude-code.md
│   ├── 06-store-instructions-memories.md
│   ├── 07-settings.md
│   ├── 08-cli-reference.md
│   ├── 09-vs-code.md
│   ├── 10-jetbrains.md
│   ├── 11-github-actions.md
│   ├── 12-gitlab-ci-cd.md
│   ├── 13-claude-code-on-the-web.md
│   ├── 14-desktop.md
│   ├── 15-chrome-extension.md
│   ├── 16-remote-control.md
│   ├── 17-slack-integration.md
│   ├── 18-mcp.md
│   ├── 19-hooks.md
│   ├── 20-sub-agents.md
│   ├── 21-plugins.md
│   ├── 22-programmatic-usage.md
│   ├── 23-security.md
│   ├── 24-data-usage.md
│   ├── 25-third-party-integrations.md
│   ├── 26-troubleshooting.md
│   └── 27-setup.md
├── preflight.py                # Main CLI script
├── scrape_docs.py              # One-time scraper to build the corpus
├── prompts/
│   ├── system_prompt.md        # The routing/extraction system prompt
│   └── output_template.md      # Output format template
├── config.yaml                 # API key location, model, token budget
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Phase 1: Build the Corpus

### 1a. Scrape the docs

A Python script (`scrape_docs.py`) that:

1. Hits each page under `https://code.claude.com/docs/en/`
2. Extracts the main content area (strips nav, footer, chrome)
3. Converts to clean markdown (using `markdownify` or `html2text`)
4. Saves each page as a numbered `.md` file in `corpus/`
5. Prepends each file with a YAML frontmatter block:

```yaml
---
title: "Best Practices"
source: "https://code.claude.com/docs/en/best-practices"
section: "Getting Started"
scraped: "2026-03-03"
---
```

**Pages to scrape** (based on the current site navigation):

| # | Slug | Section |
|---|------|---------|
| 00 | overview | Getting Started |
| 01 | quickstart | Getting Started |
| 02 | how-claude-code-works | Getting Started |
| 03 | common-workflows | Getting Started |
| 04 | best-practices | Getting Started |
| 05 | extend-claude-code | Build |
| 06 | store-instructions-memories | Build |
| 07 | settings | Configuration |
| 08 | cli-reference | Reference |
| 09 | vs-code | Platforms |
| 10 | jetbrains | Platforms |
| 11 | github-actions | Platforms |
| 12 | gitlab-ci-cd | Platforms |
| 13 | claude-code-on-the-web | Platforms |
| 14 | desktop | Platforms |
| 15 | chrome | Platforms |
| 16 | remote-control | Platforms |
| 17 | claude-code-in-slack | Platforms |
| 18 | mcp | Build |
| 19 | hooks | Build |
| 20 | sub-agents | Build |
| 21 | discover-plugins | Build |
| 22 | programmatic-usage | Build |
| 23 | security | Resources |
| 24 | data-usage | Resources |
| 25 | third-party-integrations | Deployment |
| 26 | troubleshooting | Resources |
| 27 | setup | Administration |

### 1b. Concatenate into a single corpus string

At runtime, `preflight.py` reads all files in `corpus/`, concatenates them with clear delimiters:

```
=== BEGIN DOC: Best Practices (Getting Started) ===
[source: https://code.claude.com/docs/en/best-practices]

[full markdown content]

=== END DOC: Best Practices ===
```

**Estimated total size:** ~25,000–35,000 tokens (well within a single context window).

---

## Phase 2: The Routing Prompt

This is the core of the system — a carefully designed system prompt that tells Claude how to extract and organize relevant practices.

### System Prompt (`prompts/system_prompt.md`)

```markdown
You are a Claude Code expert briefing a developer before they start a task.

You have access to the complete Claude Code documentation below. The developer
will describe what they're about to do. Your job is to:

1. Identify which docs/sections are relevant to their specific task
2. Extract the concrete, actionable best practices they should follow
3. Surface any gotchas, configuration steps, or non-obvious tips
4. Suggest the optimal workflow and permission mode for this task
5. Recommend any CLAUDE.md additions specific to this task

RULES:
- Only include practices relevant to THIS task. Do not dump everything.
- Be concrete: include actual commands, flag names, config snippets.
- If the task involves CI/CD, include the CI-specific setup steps.
- If the task involves MCP, include server configuration details.
- If the task involves multi-file edits, recommend worktrees or plan mode.
- Prioritize the "Best Practices" and "Common Workflows" docs but pull
  from anywhere in the corpus.
- Format your output as a briefing the developer can paste into their
  session or CLAUDE.md.

OUTPUT FORMAT:
## Task Understanding
[1-2 sentence restatement of what they're doing]

## Recommended Workflow
[Which mode to use, what order to do things, how to structure the session]

## Key Best Practices
[Numbered list of the most relevant practices, with concrete details]

## Configuration Checklist
[Any CLAUDE.md additions, permissions, MCP servers, or hooks to set up first]

## Watch Out For
[Gotchas, common mistakes, things that are easy to miss for this type of task]
```

### User Prompt Template

```
TASK: {user's task description}

ENVIRONMENT: {optional: IDE, OS, language/framework}

CONCERNS: {optional: speed, safety, team collaboration, CI, etc.}
```

---

## Phase 3: The CLI Script

### `preflight.py` — Core Logic

```python
#!/usr/bin/env python3
"""
Claude Code Preflight Briefing System

Usage:
  python preflight.py "I need to set up GitHub Actions to auto-review PRs"
  python preflight.py --env "VS Code, Python, macOS" "Refactor auth module"
  python preflight.py --interactive
  python preflight.py --to-clipboard "Add tests for the payment service"
"""

import argparse, os, yaml, glob
from pathlib import Path
from anthropic import Anthropic

def load_corpus(corpus_dir: str) -> str:
    """Load and concatenate all markdown files with delimiters."""
    ...

def load_system_prompt(prompts_dir: str) -> str:
    """Load the system prompt and append the full corpus."""
    ...

def build_user_message(task: str, env: str = None, concerns: str = None) -> str:
    """Format the user's input into the structured template."""
    ...

def run_preflight(task, env, concerns, config) -> str:
    """Call the Anthropic API and return the briefing."""
    client = Anthropic()
    corpus = load_corpus(config["corpus_dir"])
    system = load_system_prompt(config["prompts_dir"]) + "\n\n" + corpus
    user_msg = build_user_message(task, env, concerns)

    response = client.messages.create(
        model=config.get("model", "claude-sonnet-4-5-20250929"),
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}]
    )
    return response.content[0].text

def main():
    parser = argparse.ArgumentParser(description="Claude Code Preflight Briefing")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--env", help="Environment details")
    parser.add_argument("--concerns", help="Key concerns")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--to-clipboard", action="store_true")
    parser.add_argument("--to-file", help="Save briefing to file")
    ...
```

### Key Features

- **`--to-clipboard`**: Copies the briefing so you can paste it right into Claude Code or a CLAUDE.md
- **`--to-file`**: Saves to a file (e.g., `.claude-preflight.md` in your project)
- **`--interactive`**: Prompts you for task/env/concerns step by step
- **`--env`**: Lets you specify IDE, language, OS so the briefing is targeted
- **Caching**: Optionally cache the corpus string so it doesn't re-read files every run (minor optimization)

---

## Phase 4: Enhancements (After v1 Works)

### 4a. Add your own knowledge

Create a `corpus/custom/` directory for your own notes:
- `my-workflow-tips.md` — things you've learned from experience
- `project-specific.md` — patterns for your main projects
- `common-mistakes.md` — mistakes you keep making

These get concatenated into the corpus alongside the official docs.

### 4b. Session logging

After each Claude Code session, optionally log:
- What task you did
- What went well / what didn't
- Any new best practices discovered

These logs become future corpus entries, making the system smarter over time.

### 4c. Integration with Claude Code itself

Turn the preflight into a Claude Code custom command:

```
# ~/.claude/commands/preflight.md
Run the preflight briefing system for this task: $ARGUMENTS
Load the output into the current session context.
```

Then inside Claude Code: `/preflight refactor the auth module to use JWT`

### 4d. Corpus auto-update

A cron job or GitHub Action that:
1. Re-scrapes the docs weekly
2. Diffs against the existing corpus
3. Alerts you if anything changed
4. Auto-updates the files

---

## Build Order

| Step | What | Time Estimate |
|------|------|---------------|
| 1 | Write `scrape_docs.py` and build the corpus | 1 hour |
| 2 | Write the system prompt (`prompts/system_prompt.md`) | 30 min |
| 3 | Write `preflight.py` with basic CLI | 1 hour |
| 4 | Test with 5-10 different task types, refine the prompt | 1 hour |
| 5 | Add `--to-clipboard`, `--to-file`, `--interactive` | 30 min |
| 6 | Add custom corpus support | 30 min |
| 7 | Set up as a Claude Code custom command (optional) | 15 min |

**Total to a working v1: ~3-4 hours**

---

## Dependencies

```
# requirements.txt
anthropic>=0.40.0
requests>=2.31.0
beautifulsoup4>=4.12.0
markdownify>=0.13.0
pyyaml>=6.0
pyperclip>=1.9.0    # for clipboard support
```

---

## Config

```yaml
# config.yaml
model: claude-sonnet-4-5-20250929   # Sonnet for speed/cost; Opus for depth
corpus_dir: ./corpus
prompts_dir: ./prompts
max_tokens: 4096
cache_corpus: true
```

Use Sonnet for day-to-day preflight (fast, cheap). Switch to Opus in config if you want deeper analysis for complex tasks.
