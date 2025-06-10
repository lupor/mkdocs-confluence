![PyPI](https://img.shields.io/pypi/v/mkdocs-with-confluence)
[![Build Status](https://app.travis-ci.com/pawelsikora/mkdocs-with-confluence.svg?token=Nxwjs6L2kEPqZeJARZzo&branch=main)](https://app.travis-ci.com/pawelsikora/mkdocs-with-confluence)
[![codecov](https://codecov.io/gh/pawelsikora/mkdocs-with-confluence/branch/master/graph/badge.svg)](https://codecov.io/gh/pawelsikora/mkdocs-with-confluence)
![PyPI - Downloads](https://img.shields.io/pypi/dm/mkdocs-with-confluence)
![GitHub contributors](https://img.shields.io/github/contributors/pawelsikora/mkdocs-with-confluence)
![PyPI - License](https://img.shields.io/pypi/l/mkdocs-with-confluence)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mkdocs-with-confluence)
# mkdocs-with-confluence 

MkDocs plugin that converts markdown pages into confluence markup
and export it to the Confluence page

## Setup
Install the plugin using pip:

`pip install mkdocs-with-confluence`

Activate the plugin in `mkdocs.yml`:

```yaml
plugins:
  - search
  - mkdocs-with-confluence
```

More information about plugins in the [MkDocs documentation: mkdocs-plugins](https://www.mkdocs.org/user-guide/plugins/).

## Usage

Use following config and adjust it according to your needs:

```yaml
  - mkdocs-with-confluence:
        host_url: https://<YOUR_CONFLUENCE_DOMAIN>/rest/api/content
        space: <YOUR_SPACE>
        parent_page_name: <YOUR_ROOT_PARENT_PAGE>
        username: <YOUR_USERNAME_TO_CONFLUENCE>
        password: <YOUR_PASSWORD_TO_CONFLUENCE>
        enabled_if_env: MKDOCS_TO_CONFLUENCE
        #verbose: true
        #debug: true
        dryrun: true
```

## Parameters:

### Requirements
- md2cf
- mimetypes
- mistune

# MkDocs Confluence Plugin – Robust Internal Link & Heading Handling

## Overview
This plugin enables seamless publishing of MkDocs documentation to Confluence, with robust support for:
- Internal markdown link rewriting (including anchor links and TOC)
- Automatic mapping of internal links to Confluence URLs
- Correct anchor/TOC navigation in Confluence
- Removal of duplicate top-level headings (page titles)
- Attachment management

## Important Rule for Internal Markdown Links

When linking to another markdown file, **the link text must exactly match the target file name (without the `.md` extension) and the Confluence page name (which is taken from the first heading in the target markdown file)**. This match is case-insensitive, but the text must otherwise be identical.

- If the link text does not match the file name and Confluence page name, the plugin will not be able to rewrite the link to the correct Confluence page URL.

**Correct format:**

````markdown
[sample document](./sample document.md)
````

**Wrong format:**

````markdown
[sample file](./sample document.md)
````

> The link text (`sample document`) must match the file name (`sample document.md`) and the first heading in that file (which becomes the Confluence page name). If there is a mismatch, internal links will not work properly in Confluence.

## Key Features

### 1. Internal Link Rewriting
- All internal markdown links are rewritten to point to the correct Confluence page URLs.
- Anchor links (e.g., `[Section](#section-title)`) are preserved and work as expected in Confluence.
- The mapping is case-insensitive and uses the link text as the key.
- If a mapping is not found, the original URL is preserved.

### 2. Anchor/TOC Support
- Headings in the Confluence output include anchor macros, so TOC and anchor links work natively in Confluence.
- The plugin ensures that clicking a TOC link jumps to the correct section.

### 3. Duplicate Heading Removal
- The first heading in the page content that exactly matches the page title (case-insensitive, stripped) is automatically removed from the HTML output.
- This prevents duplicate titles in Confluence, even for nested pages.

### 4. Attachment Handling
- Local images and attachments are detected and uploaded to Confluence as page attachments.
- Existing attachments are updated only if the file content changes.

### 5. Hierarchical Page Publishing
- The plugin ensures the correct parent/child hierarchy in Confluence, creating missing parent pages as needed.

### 6. Strict Parent Page Placement
- You must provide a `parent_page_name` in your `mkdocs.yml` configuration.
- All pages described in your `nav` section will be created strictly under this specified parent page in Confluence.
- If the parent page does not exist in the current Confluence space, the plugin will automatically create it before publishing your documentation hierarchy.

> This ensures your documentation structure in Confluence always starts under the correct parent, and prevents orphaned or misplaced pages.

### 7. Page-Specific Attachment Handling
- All attachments (such as images, PDFs, and other files) referenced in a markdown file are uploaded and attached to the corresponding Confluence page.
- This ensures that each Confluence page contains only its relevant attachments, keeping your documentation organized.

### 8. Accurate Code Snippet Rendering
- Code blocks and inline code are rendered correctly in Confluence, preserving formatting, syntax highlighting, and indentation.
- This ensures technical documentation and examples are easy to read and copy from Confluence.

### 9. Table Rendering Support
- Markdown tables are converted and rendered as proper Confluence tables.
- Table formatting, alignment, and content are preserved for clear and professional documentation.

### 10. Draw.io Diagram Support
- Draw.io diagrams referenced in markdown files are exported as images and uploaded as attachments to the relevant Confluence page.
- The diagrams are displayed as images within the page content, ensuring visual documentation is preserved.

### 11. Automatic Font and Alignment Normalization
- The plugin automatically converts all font sizes and font families to a global standard (Arial, 14px for body text, and consistent heading sizes) for every published page.
- All text, headings, lists, and tables are strictly left-aligned, ensuring a uniform look across your documentation.

### 12. Modern Confluence Editor Support
- Pages are always published using the modern Confluence editor (storage format), not the legacy editor.
- This guarantees compatibility with the latest Confluence features and a consistent editing experience.

> These features ensure your documentation—including attachments, code, tables, and diagrams—appears in Confluence as intended, with no manual fixes required.

## Example Usage

Suppose you have the following markdown:

````markdown
# Getting Started

Welcome to the docs!

## Table of Contents
- [Introduction](#introduction)
- [Usage](#usage)

## Introduction
This is the introduction.

## Usage
See [Advanced Guide](Advanced Guide) for more info.

# Getting Started

This is a duplicate heading and will be removed.
````

### What happens when you publish to Confluence:
- The first `# Getting Started` is removed (since it matches the page title).
- The TOC links (`[Introduction](#introduction)`, `[Usage](#usage)`) work in Confluence and jump to the correct section.
- The link `[Advanced Guide](Advanced Guide)` is rewritten to the correct Confluence page URL if it exists.
- Any local images are uploaded as attachments.

## How to Use
1. Install the plugin and configure it in your `mkdocs.yml`.
2. Run your MkDocs build/publish process as usual.
3. The plugin will handle all internal link rewriting, heading cleanup, and attachment management automatically.

## Developer Notes
- See `plugin.py` for the main plugin logic and page processing.
- See `renderer/confluence_xhtml_renderer.py` for heading/anchor rendering.
- See `renderer/internal_link_mapper.py` for internal link rewriting logic.
- See `confluence_api/confluence_api.py` for Confluence API integration and attachment handling.

## Testing
A test is provided in `tests/test_heading_removal.py` to verify that only the first heading matching the page title is removed.

---

**This plugin ensures your MkDocs documentation is published to Confluence with correct navigation, clean headings, and robust internal linking—no manual fixes required!**
