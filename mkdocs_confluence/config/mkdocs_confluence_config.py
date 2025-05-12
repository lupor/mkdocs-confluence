from mkdocs.plugins import get_plugin_logger
import os
from mkdocs.config import base, config_options
from os import environ

log = get_plugin_logger(__name__)

class _RendererOptions(base.Config):
    strip_header = config_options.Type(bool, default=False)
    enable_relative_links = config_options.Type(bool, default=False)
    
class MkdocsConfluenceConfig(base.Config):
    host_url = config_options.Type(str, default=None)
    space = config_options.Type(str, default=None)
    parent_page_name = config_options.Type(str, default=None)
    username = config_options.Type(str, default=environ.get("CONFLUENCE_USERNAME", ""))
    api_token = config_options.Type(str, default=environ.get("CONFLUENCE_API_TOKEN", ""))
    password = config_options.Type(str, default=environ.get("CONFLUENCE_PASSWORD", ""))
    enabled_if_env = config_options.Type(str, default=None)
    verbose = config_options.Type(bool, default=False)
    debug = config_options.Type(bool, default=False)
    dryrun = config_options.Type(bool, default=False)
    renderer_options  = config_options.SubConfig(_RendererOptions)
    