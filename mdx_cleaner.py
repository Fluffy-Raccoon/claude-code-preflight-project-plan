"""
MDX Cleaner — Converts MDX components in raw doc pages to plain markdown.

Handles: Tip, Warning, Note, Info, Callout, Steps/Step, Tabs/Tab,
Accordion/AccordionGroup, Frame, CardGroup, Card, Tooltip, div, img, etc.
"""

import re
import sys
import warnings


def strip_docs_index_header(text: str) -> str:
    """Remove the '> ## Documentation Index ...' block at the top of every page."""
    # Matches the 2-line block: "> ## Documentation Index" and "> Fetch the complete..."
    pattern = r'^> ## Documentation Index\n> .*?(?=\n\n|\n[^>])'
    return re.sub(pattern, '', text, count=1, flags=re.DOTALL).lstrip('\n')


def convert_admonitions(text: str) -> str:
    """Convert <Tip>, <Warning>, <Note>, <Info>, <Callout> to blockquotes."""
    for tag in ['Tip', 'Warning', 'Note', 'Info']:
        # Multiline: <Tag>\n  content\n</Tag>
        pattern = rf'<{tag}>\s*\n(.*?)\n\s*</{tag}>'
        def replacer(m, label=tag):
            content = m.group(1).strip()
            # Indent continuation lines as blockquote
            lines = content.split('\n')
            result = f'> **{label}:** {lines[0]}'
            for line in lines[1:]:
                result += f'\n> {line.strip()}'
            return result
        text = re.sub(pattern, replacer, text, flags=re.DOTALL)

    # Callout — no label, just blockquote
    pattern = r'<Callout>\s*\n(.*?)\n\s*</Callout>'
    def callout_replacer(m):
        content = m.group(1).strip()
        lines = content.split('\n')
        return '\n'.join(f'> {line.strip()}' for line in lines)
    text = re.sub(pattern, callout_replacer, text, flags=re.DOTALL)

    return text


def convert_steps(text: str) -> str:
    """Convert <Steps>/<Step title="X"> to numbered markdown lists."""
    # First, strip outer <Steps> tags
    text = re.sub(r'<Steps>\s*', '', text)
    text = re.sub(r'\s*</Steps>', '', text)

    # Convert each <Step title="X">...</Step> to numbered items
    step_counter = [0]

    def step_replacer(m):
        step_counter[0] += 1
        title = m.group(1)
        content = m.group(2).strip()
        # Indent content under the step
        indented = '\n'.join(f'   {line}' if line.strip() else '' for line in content.split('\n'))
        return f'{step_counter[0]}. **{title}**\n{indented}'

    text = re.sub(
        r'<Step\s+title="([^"]+)">\s*\n(.*?)\n\s*</Step>',
        step_replacer,
        text,
        flags=re.DOTALL
    )

    return text


def convert_tabs(text: str) -> str:
    """Convert <Tabs>/<Tab title="X"> to subsections."""
    # Strip outer <Tabs> tags
    text = re.sub(r'<Tabs>\s*', '', text)
    text = re.sub(r'\s*</Tabs>', '', text)

    # Convert <Tab title="X">content</Tab> to ### X sections
    def tab_replacer(m):
        title = m.group(1)
        content = m.group(2).strip()
        return f'### {title}\n\n{content}'

    text = re.sub(
        r'<Tab\s+title="([^"]+)">\s*\n(.*?)\n\s*</Tab>',
        tab_replacer,
        text,
        flags=re.DOTALL
    )

    return text


def convert_accordions(text: str) -> str:
    """Convert <Accordion>/<AccordionGroup> to sections."""
    # Strip outer <AccordionGroup> tags
    text = re.sub(r'<AccordionGroup>\s*', '', text)
    text = re.sub(r'\s*</AccordionGroup>', '', text)

    # Convert <Accordion title="X">content</Accordion> to #### X sections
    def accordion_replacer(m):
        title = m.group(1)
        content = m.group(2).strip()
        return f'#### {title}\n\n{content}'

    text = re.sub(
        r'<Accordion\s+title="([^"]+)">\s*\n(.*?)\n\s*</Accordion>',
        accordion_replacer,
        text,
        flags=re.DOTALL
    )

    return text


def strip_wrapper_tags(text: str) -> str:
    """Remove wrapper tags that just contain content: Frame, CardGroup, Card, Tooltip, CodeGroup, etc."""
    # Tags to strip (keep inner content)
    for tag in ['Frame', 'CardGroup', 'Tooltip', 'CodeGroup', 'MCPServersTable']:
        text = re.sub(rf'<{tag}[^>]*>\s*', '', text)
        text = re.sub(rf'\s*</{tag}>', '', text)

    # Card with title — convert to bold title + content
    def card_replacer(m):
        attrs = m.group(1)
        content = m.group(2).strip()
        title_match = re.search(r'title="([^"]+)"', attrs)
        if title_match:
            return f'**{title_match.group(1)}**\n\n{content}'
        return content

    text = re.sub(
        r'<Card([^>]*)>\s*\n(.*?)\n\s*</Card>',
        card_replacer,
        text,
        flags=re.DOTALL
    )

    # Self-closing cards
    text = re.sub(r'<Card[^/]*/>', '', text)

    return text


def strip_html_elements(text: str) -> str:
    """Remove HTML elements like <div>, <img>, <br>, etc."""
    # Remove div tags (keep content)
    text = re.sub(r'<div[^>]*>\s*', '', text)
    text = re.sub(r'\s*</div>', '', text)

    # Remove img tags entirely
    text = re.sub(r'<img[^>]*/?\s*>', '', text)

    # Remove br tags
    text = re.sub(r'<br\s*/?>', '\n', text)

    # Remove span tags (keep content)
    text = re.sub(r'</?span[^>]*>', '', text)

    return text


def strip_remaining_unknown_tags(text: str) -> str:
    """Strip any remaining self-closing or paired tags, warning about them."""
    # Find any remaining custom component tags (capitalized)
    remaining = re.findall(r'<([A-Z][a-zA-Z]+)[\s/>]', text)
    known = {'Tip', 'Warning', 'Note', 'Info', 'Callout', 'Steps', 'Step',
             'Tabs', 'Tab', 'Accordion', 'AccordionGroup', 'Frame',
             'CardGroup', 'Card', 'Tooltip', 'CodeGroup', 'MCPServersTable',
             'EOF', 'Your'}  # EOF/Your are false positives from code examples
    for tag in set(remaining) - known:
        warnings.warn(f"Unknown MDX component found and stripped: <{tag}>")

    # Strip self-closing custom tags
    text = re.sub(r'<[A-Z][a-zA-Z]+[^>]*/>', '', text)

    # Strip opening custom tags
    text = re.sub(r'<[A-Z][a-zA-Z]+[^>]*>', '', text)

    # Strip closing custom tags
    text = re.sub(r'</[A-Z][a-zA-Z]+>', '', text)

    return text


def normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines to at most 2."""
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip() + '\n'


def clean_mdx(text: str) -> str:
    """Apply all MDX cleaning transformations in order."""
    text = strip_docs_index_header(text)
    text = convert_admonitions(text)
    text = convert_steps(text)
    text = convert_tabs(text)
    text = convert_accordions(text)
    text = strip_wrapper_tags(text)
    text = strip_html_elements(text)
    text = strip_remaining_unknown_tags(text)
    text = normalize_whitespace(text)
    return text


if __name__ == '__main__':
    # CLI usage: python mdx_cleaner.py < input.md > output.md
    text = sys.stdin.read()
    print(clean_mdx(text))
