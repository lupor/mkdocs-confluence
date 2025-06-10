from setuptools import setup, find_packages

setup(
    name="mkdocs-confluence",
    version="0.0.1",
    description="MkDocs plugin for uploading markdown documentation to Confluence via Confluence REST API",
    keywords="mkdocs markdown confluence documentation rest python",
    url="https://github.com/lupor/mkdocs-confluence/",
    author="Lupo Ribi",
    author_email="lupo.ribi@gmail.com",
    license="MIT",
    python_requires=">=3.6",
    install_requires=["mkdocs>=1.6.1", "jinja2", "requests", "mistune>=3.1.3"],
    packages=find_packages(),
    entry_points={"mkdocs.plugins": ["mkdocs-confluence = mkdocs_confluence.plugin:MkdocsConfluence"]},
)
