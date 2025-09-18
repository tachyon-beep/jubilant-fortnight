#!/usr/bin/env python3
"""Fix common markdown linting issues."""

import sys
from pathlib import Path


def fix_markdown(file_path):
    """Fix common markdown linting issues in a file."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if current line is a heading
        is_heading = line.strip().startswith('#')

        # Check if next line exists and is a list or text
        has_next = i + 1 < len(lines)
        next_is_content = has_next and lines[i + 1].strip() and not lines[i + 1].strip().startswith('#')

        # Add the current line
        new_lines.append(line)

        # If this is a heading and next line is content, add blank line
        if is_heading and next_is_content:
            new_lines.append('\n')

        # If line starts a code block and previous line isn't blank, add blank before
        if line.strip().startswith('```'):
            if new_lines and len(new_lines) >= 2 and new_lines[-2].strip():
                new_lines.insert(-1, '\n')

        i += 1

    # Ensure file ends with single newline
    while new_lines and new_lines[-1] == '\n':
        new_lines.pop()
    new_lines.append('\n')

    with open(file_path, 'w') as f:
        f.writelines(new_lines)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fix_markdown(sys.argv[1])
    else:
        # Fix all markdown files
        for md_file in Path('.').rglob('*.md'):
            if '.venv' not in str(md_file) and 'node_modules' not in str(md_file):
                print(f"Fixing {md_file}")
                fix_markdown(md_file)