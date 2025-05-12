from mkdocs.plugins import get_plugin_logger
from pathlib import Path
from typing import List, NamedTuple, Optional
from urllib.parse import unquote, urlparse
import uuid
import mistune
from mistune.renderers.html import HTMLRenderer

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

    def reinit(self):
        self.attachments = list()
        self.relative_links = list()
        self.title = None
        
    def heading(self, text, level, **attrs):
        log.debug("ENTER heading")
        if self.strip_header and level == 1:
            return ""
        return f'<h{level}>{text}</h{level}>'

    def paragraph(self, text, **attrs):
        log.debug("ENTER paragraph")
        if self.remove_text_newlines:
            text = text.replace("\n", " ")
        
        return f'<p>{text}</p>'

    def image(self, alt: str, url: str, title: Optional[str] = None) -> str:
        log.debug("ENTER image")
        attributes = {"alt": alt}
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

    def link(self, text, url, title=None):
        log.debug("ENTER link")
        parsed_link = urlparse(url)
        if (
            self.enable_relative_links
            and (not parsed_link.scheme and not parsed_link.netloc)
            and parsed_link.path
        ):
            # relative link
            replacement_link = f"md2cf-internal-link-{uuid.uuid4()}"
            self.relative_links.append(
                RelativeLink(
                    # make sure to unquote the url as relative paths
                    # might have escape sequences
                    path=unquote(parsed_link.path),
                    replacement=replacement_link,
                    fragment=parsed_link.fragment,
                    original=url,
                    escaped_original=mistune.escape_link(url),
                )
            )
            link = replacement_link
        return f'<a href="{link}">{text}</a>'

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

