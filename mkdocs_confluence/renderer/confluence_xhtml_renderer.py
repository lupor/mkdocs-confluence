from mkdocs.plugins import get_plugin_logger
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional
from urllib.parse import unquote, urlparse
import uuid
import mistune
from mistune.renderers.html import HTMLRenderer
import os
import re

log = get_plugin_logger(__name__)

class RelativeLink(NamedTuple):
    path: str
    fragment: str
    replacement: str
    original: str
    escaped_original: str


class ConfluenceTag(object):
    def __init__(self, name, text="", attrib=None, namespace="ac", cdata=False):
        self.name = name
        self.text = text
        self.namespace = namespace
        if attrib is None:
            attrib = {}
        self.attrib = attrib
        self.children = []
        self.cdata = cdata

    def render(self):
        namespaced_name = self.add_namespace(self.name, namespace=self.namespace)
        namespaced_attribs = {
            self.add_namespace(
                attribute_name, namespace=self.namespace
            ): attribute_value
            for attribute_name, attribute_value in self.attrib.items()
        }

        content = "<{}{}>{}{}</{}>".format(
            namespaced_name,
            " {}".format(
                " ".join(
                    [
                        '{}="{}"'.format(name, value)
                        for name, value in sorted(namespaced_attribs.items())
                    ]
                )
            )
            if namespaced_attribs
            else "",
            "".join([child.render() for child in self.children]),
            "<![CDATA[{}]]>".format(self.text) if self.cdata else self.text,
            namespaced_name,
        )
        return "{}\n".format(content)

    @staticmethod
    def add_namespace(tag, namespace):
        return "{}:{}".format(namespace, tag)

    def append(self, child):
        self.children.append(child)

class ConfluenceXhtmlRenderer(HTMLRenderer):
    def __init__(
        self,
        strip_header=False,
        remove_text_newlines=False,
        enable_relative_links=False,
        internal_link_map: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        log.debug("ENTER ConfluenceStorageRenderer constructor")
        log.debug("Renderer: strip_header option is set to %s", strip_header)
        self.strip_header = strip_header
        self.remove_text_newlines = remove_text_newlines
        self.attachments = list()
        self.title = None
        self.enable_relative_links = enable_relative_links
        self.relative_links: List[RelativeLink] = list()
        self.internal_link_map = internal_link_map or {}

    def reinit(self):
        self.attachments = list()
        self.relative_links = list()
        self.title = None
        
    def slugify(self, text):
        """Generate a slug for anchor links (lowercase, dash-separated, alphanumeric only)."""
        import re
        slug = text.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')

    def heading(self, text, level, **attrs):
        log.debug("ENTER heading")
        if self.strip_header and level == 1:
            return ""
        anchor_id = self.slugify(text)
        # Insert Confluence anchor macro before the heading
        anchor_macro = (
            f'<ac:structured-macro ac:name="anchor">'
            f'<ac:parameter ac:name="">{anchor_id}</ac:parameter>'
            f'</ac:structured-macro>'
        )
        return f'{anchor_macro}<h{level}>{text}</h{level}>'

    def paragraph(self, text, **attrs):
        log.debug("ENTER paragraph")
        if self.remove_text_newlines:
            text = text.replace("\n", " ")
        
        return f'<p>{text}</p>'

    def image(self, alt: str, url: str, title: Optional[str] = None) -> str:
        log.debug("ENTER image")
        attributes = {"alt": alt, "style": "max-width: 100%; height:auto", "align": "center"}
        if title:
            attributes["title"] = title

        root_element = ConfluenceTag(name="image", attrib=attributes)
        parsed_source = urlparse(url)
        if not parsed_source.netloc:
            # Local file, requires upload
            basename = Path(url).name
            url_tag = ConfluenceTag(
                "attachment", attrib={"filename": basename}, namespace="ri"
            )
            self.attachments.append(url)
        else:
            url_tag = ConfluenceTag("url", attrib={"value": url}, namespace="ri")
        root_element.append(url_tag)

        return root_element.render()

    def set_internal_link_map(self, link_map: Dict[str, str]):
        """Set or update the internal link mapping."""
        self.internal_link_map = link_map or {}
        log.debug(f"Internal link map keys: {list(self.internal_link_map.keys())}")

    def debug_print_internal_link_map(self):
        for k, v in self.internal_link_map.items():
            print(f"LINK MAP: {k} -> {v}")

    def link(self, text, url, title=None):
        parsed_link = urlparse(url)
        # Handle anchor links (e.g., [Section](#section-title))
        if url.startswith('#'):
            # Render as a local anchor link
            return f'<a href="{url}">{text}</a>'
        # Check for internal markdown link
        if (
            self.internal_link_map and
            (not parsed_link.scheme and not parsed_link.netloc) and
            parsed_link.path
        ):
            norm_path = parsed_link.path.lstrip("./\\")
            base = os.path.basename(norm_path)
            candidates = [
                url,  # the raw url as written in markdown
                norm_path,
                base,
                base[:-3] if base.endswith('.md') else base,
                norm_path[:-3] if norm_path.endswith('.md') else norm_path,
                './' + base,
                './' + (base[:-3] if base.endswith('.md') else base),
                './' + norm_path,
                './' + (norm_path[:-3] if norm_path.endswith('.md') else norm_path),
            ]
            confluence_url = None
            for key in candidates:
                if key in self.internal_link_map:
                    confluence_url = self.internal_link_map[key]
                    break
            if confluence_url:
                if parsed_link.fragment:
                    confluence_url += f"#{parsed_link.fragment}"
                return f'<a href="{confluence_url}">{text}</a>'
        # Default: external or unhandled link
        return f'<a href="{url}">{text}</a>'

    def list(self, text, ordered, **attrs):
        log.debug("ENTER list")
        # Convert lists to Confluence storage format
        tag = 'ol' if ordered else 'ul'
        return f'<{tag}>{text}</{tag}>'

    def list_item(self, text, **attrs):
        log.debug("ENTER list_item")
        # Convert list items to Confluence storage format
        return f'<li>{text}</li>'

    def block_code(self, code, info=None):
        log.debug("ENTER block_code")
        # TODO: handle mermaid diagrams
        
        key = info.split(None, 1)[0]
        language = map_language_to_confluence(key)
        
        root_element = self.structured_macro("code")
        lang_parameter = self.parameter(name="language", value=language)
        root_element.append(lang_parameter)
            
        root_element.append(self.parameter(name="linenumbers", value="true"))
        root_element.append(self.plain_text_body(code))
        return root_element.render()

    def block_quote(self, text, **attrs):
        return f'<blockquote>{text}</blockquote>'
    
    
    def inline_html(self, html):
        # check if the html is a img tag
        log.debug(f"ENTER block_html")
        log.debug(f"block_html: {html}")
        if html.startswith("<img") and html.endswith("/>"):
            src = html.split('src="')[1].split('"')[0]
            title = html.split('title="')[1].split('"')[0] if 'title="' in html else ''
            alt = html.split('alt="')[1].split('"')[0] if 'alt="' in html else ''
            return self.image(alt=alt, url=src, title=title)
        # otherwise return the html as is
        return html 

    def thematic_break(self, **attrs):
        return '<hr />'

    def structured_macro(self, name):
        print("\nDEBUG    - ENTER structured_macro }'\n")
        log.debug("ENTER structured_macro")
        return ConfluenceTag("structured-macro", attrib={"name": name})

    def parameter(self, name, value):
        parameter_tag = ConfluenceTag("parameter", attrib={"name": name})
        parameter_tag.text = value
        return parameter_tag

    def plain_text_body(self, text):
        print("\nDEBUG    - ENTER plain_text_body }'\n")
        log.debug("ENTER plain_text_body")
        body_tag = ConfluenceTag("plain-text-body", cdata=True)
        body_tag.text = text
        return body_tag
    
# Create a mapper for language names for code blocks in markdown to the corresponding name in Confluence.
# Markdown supports: https://github.com/jincheng9/markdown_supported_languages
# Confluence supports: https://confluence.atlassian.com/doc/code-block-macro-139390.html
# Default to Confluence "Shell"

def map_language_to_confluence(markdown_language):
    # Define a mapping between Markdown and Confluence languages
    language_map = {
        'python': 'python',
        'javascript': 'javascript',
        'java': 'java',
        'html': 'html',
        'css': 'css',
        'bash': 'bash',
        'shell': 'bash',
        'json': 'json',
        'xml': 'xml',
        'yaml': 'yaml',
        'c': 'c',
        'cpp': 'cpp',
        'c++': 'cpp',
        'php': 'php',
        'ruby': 'ruby',
        'perl': 'perl',
        'sql': 'sql',
        'swift': 'swift',
        'go': 'go',
        'kotlin': 'kotlin',
        'typescript': 'typescript',
        # Add more mappings as needed
    }
    # Return the mapped language or default to "bash" (Confluence "Shell")
    if not markdown_language:
        return 'bash'
    return language_map.get(markdown_language.lower(), 'bash')

