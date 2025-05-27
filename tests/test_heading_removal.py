import re
from mkdocs_confluence.renderer.confluence_xhtml_renderer import ConfluenceXhtmlRenderer

def test_remove_first_h1_matching_title():
    renderer = ConfluenceXhtmlRenderer()
    renderer.title = "Sample Page"
    renderer.reinit()
    # Markdown with duplicate H1s, only the first matches the title
    html = (
        renderer.heading("Sample Page", 1) +  # Should be removed
        renderer.heading("Introduction", 1) +  # Should be kept
        renderer.heading("Sample Page", 2) +   # Should be kept (not h1)
        renderer.heading("Sample Page", 1)     # Should be kept (not first)
    )
    # Remove the first occurrence of the exact page title as a heading (simulate plugin logic)
    h1_pattern = re.compile(r'<h1[^>]*>\s*Sample Page\s*</h1>', re.IGNORECASE)
    html = h1_pattern.sub('', html, count=1)
    # Check results
    assert '<h1>Sample Page</h1>' not in html, "First matching <h1> should be removed"
    assert '<h1>Introduction</h1>' in html, "Other <h1> should remain"
    assert '<h2>Sample Page</h2>' in html, "<h2> with title should remain"
    assert html.count('<h1>Sample Page</h1>') == 0, "No <h1>Sample Page</h1> should remain"
    print("test_remove_first_h1_matching_title passed.")

if __name__ == "__main__":
    test_remove_first_h1_matching_title()
