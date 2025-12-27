#!/usr/bin/env python3
"""
WeaveExpressionUI HTML Builder

Combines template HTML with Base64 image data to produce the final HTML.

Usage:
    python build_html.py

Input:
    - WeaveExpressionUI.template.html (template with placeholder)
    - expression_images.json (Base64 image data)

Output:
    - WeaveExpressionUI.html (final HTML with embedded images)
"""

import json
import os

def build():
    # Read template
    with open('WeaveExpressionUI.template.html', 'r', encoding='utf-8') as f:
        template = f.read()

    # Read image data
    with open('expression_images.json', 'r') as f:
        images = json.load(f)

    # Build images object string
    images_str = ','.join([f"{k}:'{v}'" for k, v in images.items()])

    # Replace placeholder
    html = template.replace('__IMAGES_PLACEHOLDER__', images_str)

    # Write output
    with open('WeaveExpressionUI.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Built WeaveExpressionUI.html ({os.path.getsize("WeaveExpressionUI.html") / 1024:.1f} KB)')

if __name__ == '__main__':
    build()
