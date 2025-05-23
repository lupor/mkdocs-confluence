import re

# --- Internal Link Rewriting for MkDocs Confluence Plugin ---

def rewrite_internal_links(markdown: str, page_link_map: dict) -> str:
    """
    Replace all internal markdown links with their Confluence URLs using the link text as the key.
    - If the link text (case-insensitive) matches a key in the dict, replace the URL with the value (Confluence link).
    - If not found, keep the original URL.
    """
    def replacer(match):
        text = match.group(1).strip()
        url = match.group(2).strip()
        # Case-insensitive lookup for the link text
        lookup_text = text.lower()
        page_link_map_lower = {k.lower(): v for k, v in page_link_map.items()}
        confluence_url = page_link_map_lower.get(lookup_text)
        if confluence_url:
            # Keep fragment if present
            if '#' in url:
                confluence_url += '#' + url.split('#', 1)[1]
            return f'[{text}]({confluence_url})'
        # If not found, keep the original URL
        return f'[{text}]({url})'
    # Replace all markdown links in the content
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replacer, markdown)


def build_page_link_map(page_link_dict):
    """
    Return the provided dict as the page link map. (For future extensibility.)
    """
    return page_link_dict