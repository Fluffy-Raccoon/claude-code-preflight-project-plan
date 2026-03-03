#!/usr/bin/env python3
"""
Scrape Claude Code documentation from code.claude.com/docs.

Fetches the llms.txt index, downloads each page as raw markdown,
cleans MDX components, adds YAML frontmatter, and saves to corpus/.

Usage:
  python scrape_docs.py                  # Scrape all docs
  python scrape_docs.py --force          # Re-scrape even if files exist
  python scrape_docs.py --dry-run        # Show what would be fetched
  python scrape_docs.py --output corpus  # Custom output directory
"""

import argparse
import os
import re
import sys
import time
from datetime import date

import requests

from mdx_cleaner import clean_mdx

LLMS_TXT_URL = "https://code.claude.com/docs/llms.txt"
BASE_URL = "https://code.claude.com/docs/en"

# Slug -> section mapping for all 59 pages
SECTION_MAP = {
    # Getting Started
    "overview": "Getting Started",
    "quickstart": "Getting Started",
    "how-claude-code-works": "Getting Started",
    "common-workflows": "Getting Started",
    "best-practices": "Getting Started",

    # Configuration
    "settings": "Configuration",
    "memory": "Configuration",
    "permissions": "Configuration",
    "model-config": "Configuration",
    "keybindings": "Configuration",
    "output-styles": "Configuration",
    "statusline": "Configuration",
    "terminal-config": "Configuration",
    "fast-mode": "Configuration",

    # Build & Extend
    "features-overview": "Build & Extend",
    "skills": "Build & Extend",
    "hooks-guide": "Build & Extend",
    "hooks": "Build & Extend",
    "plugins": "Build & Extend",
    "plugins-reference": "Build & Extend",
    "discover-plugins": "Build & Extend",
    "plugin-marketplaces": "Build & Extend",
    "mcp": "Build & Extend",

    # Agents & Automation
    "sub-agents": "Agents & Automation",
    "agent-teams": "Agents & Automation",
    "headless": "Agents & Automation",
    "interactive-mode": "Agents & Automation",
    "authentication": "Agents & Automation",

    # Platforms
    "vs-code": "Platforms",
    "jetbrains": "Platforms",
    "desktop": "Platforms",
    "desktop-quickstart": "Platforms",
    "claude-code-on-the-web": "Platforms",
    "chrome": "Platforms",
    "remote-control": "Platforms",
    "slack": "Platforms",

    # CI/CD & Deployment
    "github-actions": "CI/CD & Deployment",
    "gitlab-ci-cd": "CI/CD & Deployment",
    "third-party-integrations": "CI/CD & Deployment",

    # Enterprise & Administration
    "setup": "Enterprise & Administration",
    "amazon-bedrock": "Enterprise & Administration",
    "google-vertex-ai": "Enterprise & Administration",
    "microsoft-foundry": "Enterprise & Administration",
    "server-managed-settings": "Enterprise & Administration",
    "llm-gateway": "Enterprise & Administration",
    "network-config": "Enterprise & Administration",
    "analytics": "Enterprise & Administration",
    "monitoring-usage": "Enterprise & Administration",

    # Security & Compliance
    "security": "Security & Compliance",
    "data-usage": "Security & Compliance",
    "sandboxing": "Security & Compliance",
    "zero-data-retention": "Security & Compliance",
    "legal-and-compliance": "Security & Compliance",

    # Resources
    "troubleshooting": "Resources",
    "checkpointing": "Resources",
    "devcontainer": "Resources",
    "costs": "Resources",
    "cli-reference": "Resources",
    "changelog": "Resources",
}

# Ordering for numbered filenames — defines the canonical order within sections
SECTION_ORDER = [
    "Getting Started",
    "Configuration",
    "Build & Extend",
    "Agents & Automation",
    "Platforms",
    "CI/CD & Deployment",
    "Enterprise & Administration",
    "Security & Compliance",
    "Resources",
]


def fetch_page_index() -> list[dict]:
    """Fetch llms.txt and parse into a list of page entries."""
    print(f"Fetching index from {LLMS_TXT_URL}...")
    resp = requests.get(LLMS_TXT_URL, timeout=30)
    resp.raise_for_status()

    entries = []
    # Each line is like: [Title](https://code.claude.com/docs/en/slug.md): Description
    pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    for line in resp.text.strip().split('\n'):
        m = pattern.search(line)
        if m:
            title = m.group(1)
            url = m.group(2)
            # Extract slug from URL
            slug = url.rstrip('/').split('/')[-1]
            if slug.endswith('.md'):
                slug = slug[:-3]
            entries.append({
                "title": title,
                "slug": slug,
                "url": url,
            })

    print(f"Found {len(entries)} pages in index.")
    return entries


def fetch_page_content(url: str) -> str:
    """Fetch a single markdown page."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def build_frontmatter(title: str, slug: str, source_url: str, section: str) -> str:
    """Generate YAML frontmatter block."""
    return (
        f"---\n"
        f'title: "{title}"\n'
        f'slug: "{slug}"\n'
        f'source: "{source_url}"\n'
        f'section: "{section}"\n'
        f'scraped: "{date.today().isoformat()}"\n'
        f"---\n"
    )


def sort_entries(entries: list[dict]) -> list[dict]:
    """Sort entries by section order, then alphabetically within section."""
    def sort_key(entry):
        section = SECTION_MAP.get(entry["slug"], "Resources")
        section_idx = SECTION_ORDER.index(section) if section in SECTION_ORDER else 99
        return (section_idx, entry["slug"])
    return sorted(entries, key=sort_key)


def scrape_all(output_dir: str = "corpus", force: bool = False, dry_run: bool = False):
    """Fetch all doc pages and save as numbered markdown files."""
    os.makedirs(output_dir, exist_ok=True)

    entries = fetch_page_index()
    entries = sort_entries(entries)

    if dry_run:
        print(f"\nDry run — would fetch {len(entries)} pages:\n")
        for i, entry in enumerate(entries):
            section = SECTION_MAP.get(entry["slug"], "Unknown")
            filename = f"{i:02d}-{entry['slug']}.md"
            print(f"  {filename}  [{section}]  {entry['title']}")
        return

    print(f"\nScraping {len(entries)} pages to {output_dir}/...\n")

    for i, entry in enumerate(entries):
        slug = entry["slug"]
        title = entry["title"]
        url = entry["url"]
        section = SECTION_MAP.get(slug, "Unknown")
        filename = f"{i:02d}-{slug}.md"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath) and not force:
            print(f"  [{i+1:2d}/{len(entries)}] SKIP {filename} (exists, use --force)")
            continue

        print(f"  [{i+1:2d}/{len(entries)}] Fetching {slug}...", end=" ", flush=True)

        try:
            raw = fetch_page_content(url)
            cleaned = clean_mdx(raw)
            source_url = f"{BASE_URL}/{slug}"
            frontmatter = build_frontmatter(title, slug, source_url, section)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter + "\n" + cleaned)

            print(f"OK ({len(cleaned):,} chars)")
        except Exception as e:
            print(f"FAILED: {e}")

        # Be polite — 1 second between requests
        if i < len(entries) - 1:
            time.sleep(1)

    print(f"\nDone. Corpus saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Claude Code docs into a local corpus"
    )
    parser.add_argument(
        "--output", "-o", default="corpus",
        help="Output directory (default: corpus)"
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Re-scrape even if files already exist"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be fetched without writing"
    )

    args = parser.parse_args()
    scrape_all(output_dir=args.output, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
