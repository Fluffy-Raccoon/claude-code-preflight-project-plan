#!/usr/bin/env python3
"""
Claude Code Preflight Briefing System

Takes a plain-English task description and returns a focused briefing of the
most relevant Claude Code best practices, workflows, and configuration tips.

Usage:
  python preflight.py "Set up GitHub Actions to auto-review PRs"
  python preflight.py --env "VS Code, Python, macOS" "Refactor auth module"
  python preflight.py --interactive
  python preflight.py --to-clipboard "Add tests for the payment service"
  python preflight.py --to-file briefing.md "Migrate React app to TypeScript"
"""

import argparse
import glob
import hashlib
import os
import sys
import time
from pathlib import Path

import yaml
from anthropic import Anthropic

# Load .env file if present (for ANTHROPIC_API_KEY)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv is optional


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    script_dir = Path(__file__).parent
    full_path = script_dir / config_path if not os.path.isabs(config_path) else Path(config_path)

    if not full_path.exists():
        # Return defaults if config doesn't exist
        return {
            "model": "claude-sonnet-4-6",
            "corpus_dir": "./corpus",
            "custom_corpus_dir": "./corpus_custom",
            "prompts_dir": "./prompts",
            "max_tokens": 4096,
            "cache_corpus": True,
        }

    with open(full_path, 'r') as f:
        return yaml.safe_load(f)


def resolve_path(config_path: str) -> Path:
    """Resolve a config path relative to the script directory."""
    script_dir = Path(__file__).parent
    p = Path(config_path)
    if p.is_absolute():
        return p
    return script_dir / p


# Files to exclude from corpus (too large or not useful for preflight)
CORPUS_EXCLUDE = {'changelog'}

# Max chars per doc file. Docs exceeding this are truncated to keep total
# corpus within ~150K tokens (well within the 200K context window).
MAX_DOC_CHARS = 15_000


def truncate_content(content: str, max_chars: int) -> str:
    """Truncate content at a clean boundary (end of paragraph/section)."""
    if len(content) <= max_chars:
        return content

    # Find a good break point: last double-newline before the limit
    truncated = content[:max_chars]
    last_break = truncated.rfind('\n\n')
    if last_break > max_chars * 0.7:  # Only use break if it's in the last 30%
        truncated = truncated[:last_break]

    return truncated + "\n\n[... truncated — see full doc for details]"


def load_corpus(corpus_dir: str, custom_corpus_dir: str = None,
                max_doc_chars: int = MAX_DOC_CHARS) -> str:
    """Load and concatenate all markdown files from corpus directories with delimiters."""
    parts = []
    total_chars = 0

    for directory in [corpus_dir, custom_corpus_dir]:
        if directory is None:
            continue
        dir_path = resolve_path(directory)
        if not dir_path.exists():
            continue

        md_files = sorted(dir_path.glob("*.md"))
        for filepath in md_files:
            if filepath.name == '.gitkeep':
                continue

            # Skip excluded files (e.g., changelog is 1.2M chars)
            slug = filepath.stem.split('-', 1)[-1] if '-' in filepath.stem else filepath.stem
            if slug in CORPUS_EXCLUDE:
                continue

            content = filepath.read_text(encoding='utf-8')

            # Parse frontmatter to get title and section
            title = filepath.stem
            section = ""
            source = ""

            if content.startswith('---'):
                parts_fm = content.split('---', 2)
                if len(parts_fm) >= 3:
                    try:
                        fm = yaml.safe_load(parts_fm[1])
                        if fm:
                            title = fm.get('title', title)
                            section = fm.get('section', '')
                            source = fm.get('source', '')
                        content = parts_fm[2].strip()
                    except yaml.YAMLError:
                        pass

            # Truncate long docs to stay within token budget
            content = truncate_content(content, max_doc_chars)
            total_chars += len(content)

            section_label = f" ({section})" if section else ""
            source_line = f"\n[source: {source}]" if source else ""

            parts.append(
                f"=== BEGIN DOC: {title}{section_label} ==={source_line}\n\n"
                f"{content}\n\n"
                f"=== END DOC: {title} ==="
            )

    return "\n\n".join(parts)


def get_cached_corpus(corpus_dir: str, custom_corpus_dir: str = None,
                      cache_enabled: bool = True, max_doc_chars: int = MAX_DOC_CHARS) -> str:
    """Return cached corpus if valid, otherwise rebuild."""
    cache_path = resolve_path(corpus_dir) / ".corpus_cache"
    hash_path = resolve_path(corpus_dir) / ".corpus_hash"

    if not cache_enabled:
        return load_corpus(corpus_dir, custom_corpus_dir, max_doc_chars)

    # Compute hash of all corpus files
    hasher = hashlib.md5()
    for directory in [corpus_dir, custom_corpus_dir]:
        if directory is None:
            continue
        dir_path = resolve_path(directory)
        if not dir_path.exists():
            continue
        for filepath in sorted(dir_path.glob("*.md")):
            hasher.update(filepath.read_bytes())
    current_hash = hasher.hexdigest()

    # Check if cache is valid
    if cache_path.exists() and hash_path.exists():
        cached_hash = hash_path.read_text().strip()
        if cached_hash == current_hash:
            return cache_path.read_text(encoding='utf-8')

    # Rebuild cache
    corpus = load_corpus(corpus_dir, custom_corpus_dir, max_doc_chars)
    cache_path.write_text(corpus, encoding='utf-8')
    hash_path.write_text(current_hash)
    return corpus


def load_system_prompt(prompts_dir: str) -> str:
    """Load system prompt and output template, concatenated."""
    dir_path = resolve_path(prompts_dir)

    system_prompt = ""
    template = ""

    sp_path = dir_path / "system_prompt.md"
    if sp_path.exists():
        system_prompt = sp_path.read_text(encoding='utf-8').strip()

    tpl_path = dir_path / "output_template.md"
    if tpl_path.exists():
        template = tpl_path.read_text(encoding='utf-8').strip()

    if template:
        return f"{system_prompt}\n\n{template}"
    return system_prompt


def build_user_message(task: str, env: str = None, concerns: str = None) -> str:
    """Format the user's input into the structured template."""
    msg = f"TASK: {task}"
    if env:
        msg += f"\n\nENVIRONMENT: {env}"
    if concerns:
        msg += f"\n\nCONCERNS: {concerns}"
    return msg


def run_preflight(task: str, env: str = None, concerns: str = None,
                  config: dict = None) -> dict:
    """
    Call the Anthropic API and return the briefing.
    Returns a dict with 'text', 'input_tokens', 'output_tokens'.
    """
    if config is None:
        config = load_config("config.yaml")

    client = Anthropic()

    corpus = get_cached_corpus(
        config.get("corpus_dir", "./corpus"),
        config.get("custom_corpus_dir", "./corpus_custom"),
        config.get("cache_corpus", True),
        config.get("max_doc_chars", MAX_DOC_CHARS),
    )

    system_prompt = load_system_prompt(config.get("prompts_dir", "./prompts"))
    user_msg = build_user_message(task, env, concerns)

    # Use structured system messages with prompt caching on the corpus
    response = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=config.get("max_tokens", 4096),
        system=[
            {"type": "text", "text": system_prompt},
            {
                "type": "text",
                "text": f"DOCUMENTATION CORPUS:\n\n{corpus}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": user_msg}],
    )

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, 'cache_creation_input_tokens', 0),
        "cache_read_input_tokens": getattr(response.usage, 'cache_read_input_tokens', 0),
    }


def interactive_prompt() -> tuple[str, str, str]:
    """Prompt the user interactively for task, environment, and concerns."""
    print("Claude Code Preflight Briefing System")
    print("=" * 40)
    print()

    task = input("What task are you about to do?\n> ").strip()
    if not task:
        print("Error: Task description is required.")
        sys.exit(1)

    env = input("\nEnvironment details (IDE, OS, language/framework)? [optional]\n> ").strip()
    concerns = input("\nKey concerns (speed, safety, collaboration, etc.)? [optional]\n> ").strip()

    return task, env or None, concerns or None


# --- Smart Scope-to-Preflight (Pass 1) ---

MAX_SCOPE_CHARS = 20_000


def load_scope_files(scope_dir: str = None, scope_files: list[str] = None) -> str:
    """Load and concatenate project scope markdown files with delimiters."""
    files_to_read = []

    if scope_files:
        # Use specific files provided via --scope-files
        for f in scope_files:
            p = Path(f)
            if not p.exists():
                print(f"Error: Scope file '{f}' not found.", file=sys.stderr)
                sys.exit(1)
            files_to_read.append(p)
    else:
        # Use all .md files from scope directory
        dir_path = resolve_path(scope_dir or "./scope")
        if not dir_path.exists():
            print(f"Error: Scope directory '{dir_path}' not found.", file=sys.stderr)
            print("Create it and add .md files describing your project, "
                  "or use --scope-dir to specify a different path.", file=sys.stderr)
            sys.exit(1)

        files_to_read = sorted(
            p for p in dir_path.glob("*.md") if p.name != '.gitkeep'
        )

    if not files_to_read:
        print("Error: No .md files found in scope directory.", file=sys.stderr)
        print("Add project scope files (e.g., project-overview.md, tech-stack.md) "
              "and try again.", file=sys.stderr)
        sys.exit(1)

    parts = []
    for filepath in files_to_read:
        content = filepath.read_text(encoding='utf-8').strip()
        content = truncate_content(content, MAX_SCOPE_CHARS)
        parts.append(
            f"=== SCOPE: {filepath.name} ===\n\n"
            f"{content}\n\n"
            f"=== END SCOPE: {filepath.name} ==="
        )

    return "\n\n".join(parts)


def load_scope_prompt(prompts_dir: str) -> str:
    """Load the scope-to-task system prompt."""
    dir_path = resolve_path(prompts_dir)
    sp_path = dir_path / "scope_prompt.md"
    if not sp_path.exists():
        print(f"Error: Scope prompt not found at {sp_path}", file=sys.stderr)
        sys.exit(1)
    return sp_path.read_text(encoding='utf-8').strip()


def parse_generated_task(text: str) -> dict:
    """Parse the generated task description into task, env, and concerns fields."""
    result = {"task": "", "env": None, "concerns": None}

    current_key = None
    current_lines = []

    for line in text.strip().split('\n'):
        if line.startswith("TASK:"):
            if current_key:
                result[current_key] = '\n'.join(current_lines).strip()
            current_key = "task"
            current_lines = [line[5:].strip()]
        elif line.startswith("ENVIRONMENT:"):
            if current_key:
                result[current_key] = '\n'.join(current_lines).strip()
            current_key = "env"
            current_lines = [line[12:].strip()]
        elif line.startswith("CONCERNS:"):
            if current_key:
                result[current_key] = '\n'.join(current_lines).strip()
            current_key = "concerns"
            current_lines = [line[9:].strip()]
        else:
            current_lines.append(line)

    if current_key:
        result[current_key] = '\n'.join(current_lines).strip()

    # Fallback: if no structured format detected, treat entire output as task
    if not result["task"]:
        result["task"] = text.strip()

    return result


def generate_task_from_scope(scope_content: str, config: dict) -> dict:
    """
    Pass 1: Generate an optimal preflight task description from scope files.
    Uses a lighter/faster model. Does NOT load the docs corpus.
    """
    client = Anthropic()

    scope_prompt = load_scope_prompt(config.get("prompts_dir", "./prompts"))

    response = client.messages.create(
        model=config.get("scope_model", "claude-haiku-4-5-20251001"),
        max_tokens=config.get("scope_max_tokens", 1024),
        system=scope_prompt,
        messages=[{
            "role": "user",
            "content": f"PROJECT SCOPE FILES:\n\n{scope_content}",
        }],
    )

    text = response.content[0].text
    parsed = parse_generated_task(text)

    return {
        **parsed,
        "raw_output": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def review_generated_task(task: str, env: str = None,
                          concerns: str = None) -> tuple[str, str, str]:
    """Display the generated task description and let the user approve or edit."""
    print("\n" + "=" * 50)
    print("GENERATED TASK DESCRIPTION")
    print("=" * 50)
    print(f"\nTASK: {task}")
    if env:
        print(f"\nENVIRONMENT: {env}")
    if concerns:
        print(f"\nCONCERNS: {concerns}")
    print("\n" + "-" * 50)

    choice = input("\n[A]pprove, [E]dit, or [Q]uit? > ").strip().lower()

    if choice in ('q', 'quit'):
        print("Aborted.")
        sys.exit(0)
    elif choice in ('e', 'edit'):
        print("\nEdit each field (press Enter to keep current value):\n")
        new_task = input(f"TASK:\n> ").strip()
        new_env = input(f"\nENVIRONMENT:\n> ").strip()
        new_concerns = input(f"\nCONCERNS:\n> ").strip()
        return (
            new_task or task,
            new_env or env,
            new_concerns or concerns,
        )
    else:
        # Default: approve
        return task, env, concerns


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Preflight Briefing System",
        epilog=(
            "Examples:\n"
            '  python preflight.py "Set up GitHub Actions for PR review"\n'
            '  python preflight.py --env "VS Code, Python" "Refactor auth module"\n'
            '  python preflight.py --interactive\n'
            '  python preflight.py -c "Add payment tests"\n'
            '  python preflight.py --from-scope\n'
            '  python preflight.py --from-scope --scope-dir ./docs/ -y -c\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--env", "-e", help="Environment: IDE, OS, language/framework")
    parser.add_argument("--concerns", help="Key concerns: speed, safety, etc.")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode: prompts for task/env/concerns")
    parser.add_argument("--to-clipboard", "-c", action="store_true",
                        help="Copy briefing to clipboard")
    parser.add_argument("--to-file", "-f", help="Save briefing to file")
    parser.add_argument("--model", "-m", help="Override model (e.g., claude-opus-4-6)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show token usage and timing")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config file (default: config.yaml)")

    # Smart scope-to-preflight flags
    parser.add_argument("--from-scope", "-s", action="store_true",
                        help="Generate task description from project scope files")
    parser.add_argument("--scope-dir", default=None,
                        help="Directory containing scope .md files (default: ./scope/)")
    parser.add_argument("--scope-files", nargs="+", default=None,
                        help="Specific scope .md files to use")
    parser.add_argument("--auto-approve", "-y", action="store_true",
                        help="Skip review of generated task description")
    parser.add_argument("--scope-model", default=None,
                        help="Model for task generation (default: claude-haiku-4-5)")

    args = parser.parse_args()

    # Load config and apply overrides
    config = load_config(args.config)
    if args.model:
        config["model"] = args.model
    if args.scope_model:
        config["scope_model"] = args.scope_model

    # --- Input routing: three paths ---
    if args.from_scope:
        # Pass 1: Generate task from scope files
        scope_dir = args.scope_dir or config.get("scope_dir", "./scope")
        scope_content = load_scope_files(
            scope_dir=scope_dir,
            scope_files=args.scope_files,
        )

        scope_model = config.get("scope_model", "claude-haiku-4-5-20251001")
        print(f"\nGenerating task description from scope files using {scope_model}...")

        try:
            scope_result = generate_task_from_scope(scope_content, config)
        except Exception as e:
            print(f"Error in Pass 1 (scope generation): {e}", file=sys.stderr)
            if "ANTHROPIC_API_KEY" in str(e) or "api_key" in str(e).lower():
                print("\nHint: Set your API key with: export ANTHROPIC_API_KEY=sk-ant-...",
                      file=sys.stderr)
            sys.exit(1)

        task = scope_result["task"]
        env = scope_result.get("env") or args.env
        concerns = scope_result.get("concerns") or args.concerns

        if args.verbose:
            print(f"(Pass 1: {scope_result['input_tokens']:,} in / "
                  f"{scope_result['output_tokens']:,} out)")

        # Review step (unless --auto-approve)
        if not args.auto_approve:
            task, env, concerns = review_generated_task(task, env, concerns)
        else:
            print(f"\nTASK: {task}")
            if env:
                print(f"ENVIRONMENT: {env}")
            if concerns:
                print(f"CONCERNS: {concerns}")

    elif args.interactive:
        task, env, concerns = interactive_prompt()
    elif args.task:
        task = args.task
        env = args.env
        concerns = args.concerns
    else:
        parser.print_help()
        sys.exit(1)

    # Run the preflight briefing
    print(f"\nGenerating briefing using {config.get('model', 'claude-sonnet-4-6')}...\n")
    start_time = time.time()

    try:
        result = run_preflight(task, env, concerns, config)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if "ANTHROPIC_API_KEY" in str(e) or "api_key" in str(e).lower():
            print("\nHint: Set your API key with: export ANTHROPIC_API_KEY=sk-ant-...",
                  file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    briefing = result["text"]

    # Print the briefing
    print(briefing)

    # Verbose output
    if args.verbose:
        print(f"\n{'=' * 40}")
        print(f"Model: {config.get('model', 'claude-sonnet-4-6')}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Input tokens: {result['input_tokens']:,}")
        print(f"Output tokens: {result['output_tokens']:,}")
        if result.get('cache_creation_input_tokens'):
            print(f"Cache creation tokens: {result['cache_creation_input_tokens']:,}")
        if result.get('cache_read_input_tokens'):
            print(f"Cache read tokens: {result['cache_read_input_tokens']:,}")

    # Copy to clipboard
    if args.to_clipboard:
        try:
            import pyperclip
            pyperclip.copy(briefing)
            print("\n(Briefing copied to clipboard)")
        except Exception as e:
            print(f"\nCouldn't copy to clipboard: {e}", file=sys.stderr)
            print("Try --to-file instead.", file=sys.stderr)

    # Save to file
    if args.to_file:
        with open(args.to_file, 'w', encoding='utf-8') as f:
            f.write(briefing)
        print(f"\n(Briefing saved to {args.to_file})")


if __name__ == "__main__":
    main()
