import logging
from mkdocs.plugins import get_plugin_logger
import time
import os
import hashlib
import re
import tempfile
import shutil
import requests
import mimetypes
import mistune
from time import sleep
from mkdocs.plugins import BasePlugin
from pathlib import Path

from mkdocs_confluence.config.mkdocs_confluence_config import *
from mkdocs_confluence.confluence_api.confluence_api import ConfluenceAPI
from mkdocs_confluence.renderer.confluence_xhtml_renderer import ConfluenceXhtmlRenderer

TEMPLATE_BODY = "<p> TEMPLATE </p>"

log = get_plugin_logger(__name__)

class MkdocsConfluence(BasePlugin[MkdocsConfluenceConfig]):
    _id = 0

    def __init__(self):
        self.enabled = True
        self.simple_log = False
        self.flen = 1
        self.page_attachments = {}

    def on_nav(self, nav, config, files):
        MkdocsConfluence.tab_nav = []
        navigation_items = nav.__repr__()
        for n in navigation_items.split("\n"):
            leading_spaces = len(n) - len(n.lstrip(" "))
            spaces = leading_spaces * " "
            if "Page" in n:
                try:
                    self.page_title = self.__get_page_title(n)
                    if self.page_title is None:
                        raise AttributeError
                except AttributeError:
                    self.page_local_path = self.__get_page_url(n)
                    print(
                        f"WARN    - Page from path {self.page_local_path} has no"
                        f"          entity in the mkdocs.yml nav section. It will be uploaded"
                        f"          to the Confluence, but you may not see it on the web server!"
                    )
                    self.page_local_name = self.__get_page_name(n)
                    self.page_title = self.page_local_name

                p = spaces + self.page_title
                MkdocsConfluence.tab_nav.append(p)
            if "Section" in n:
                try:
                    self.section_title = self.__get_section_title(n)
                    if self.section_title is None:
                        raise AttributeError
                except AttributeError:
                    self.section_local_path = self.__get_page_url(n)
                    print(
                        f"WARN    - Section from path {self.section_local_path} has no"
                        f"          entity in the mkdocs.yml nav section. It will be uploaded"
                        f"          to the Confluence, but you may not see it on the web server!"
                    )
                    self.section_local_name = self.__get_section_title(n)
                    self.section_title = self.section_local_name
                s = spaces + self.section_title
                MkdocsConfluence.tab_nav.append(s)

    def on_files(self, files, config):
        pages = files.documentation_pages()
        try:
            self.flen = len(pages)
            print(f"Number of Files in directory tree: {self.flen}")
        except 0:
            print("ERR: You have no documentation pages" "in the directory tree, please add at least one!")

    def on_post_template(self, output_content, template_name, config):
        log.info("Start exporting markdown pages...")

    def on_config(self, config):
        if self.config["dryrun"]:
            log.warning("DRYRUN MODE turned ON")
            self.dryrun = True
        else:
            self.dryrun = False
        
        self.__configure_renderer()
        self.__configure_http_client()
        has_environment_flag = "enabled_if_env" in self.config
        flag_name = self.config["enabled_if_env"]
        
        if len(flag_name) == 0:
            log.warning("no valid environement variable name provided with 'enabled_if_env' will default to true")
            self.enabled = True
            return  
        
        flag_enabled = has_environment_flag and flag_name and os.environ.get(flag_name) == "1"
        
        
        if has_environment_flag and flag_enabled == False:
            log.warning(
                "Export to Confluence turned OFF: "
                f"(set environment variable {flag_name} to 1 to enable)"
            )
        
        if has_environment_flag and flag_enabled:
            log.info(
                "Export to Confluence "
                f"turned ON by var {flag_name}==1!"
            )
        
        self.enabled = flag_enabled if has_environment_flag else True


    def on_page_markdown(self, markdown, page, config, files):
        MkdocsConfluence._id += 1
        failed_pages = []  # Track failed pages

        if self.enabled:
            if self.simple_log is True:
                print("INFO    - Mkdocs With Confluence: Page export progress: [", end="", flush=True)
                for i in range(MkdocsConfluence._id):
                    print("#", end="", flush=True)
                for j in range(self.flen - MkdocsConfluence._id):
                    print("-", end="", flush=True)
                print(f"] ({MkdocsConfluence._id} / {self.flen})", end="\r", flush=True)

            log.debug("Handling Page '{page.title}' (And Parent Nav Pages if necessary):")
            if not all(self.config_scheme):
                log.debug("ERR: YOU HAVE EMPTY VALUES IN YOUR CONFIG. ABORTING")
                return markdown

            try:
                log.debug("Get section first parent title...: ")
                try:

                    parent = self.__get_section_title(page.ancestors[0].__repr__())
                except IndexError as e:
                    if self.config["debug"]:
                        print(
                            f"DEBUG    - WRN({e}): No first parent! Assuming "
                            f"DEBUG    - {self.config['parent_page_name']}..."
                        )
                    parent = None
                if self.config["debug"]:
                    print(f"DEBUG    - {parent}")
                if not parent:
                    parent = self.config["parent_page_name"]

                if self.config["parent_page_name"] is not None:
                    main_parent = self.config["parent_page_name"]
                else:
                    main_parent = self.config["space"]

                if self.config["debug"]:
                    print("DEBUG    - Get section second parent title...: ")
                try:
                    parent1 = self.__get_section_title(page.ancestors[1].__repr__())
                except IndexError as e:
                    if self.config["debug"]:
                        print(
                            f"DEBUG    - ERR({e}) No second parent! Assuming "
                            f"second parent is main parent: {main_parent}..."
                        )
                    parent1 = None
                if self.config["debug"]:
                    print(f"{parent}")

                if not parent1:
                    parent1 = main_parent
                    if self.config["debug"]:
                        print(
                            f"DEBUG    - ONLY ONE PARENT FOUND. ASSUMING AS A "
                            f"FIRST NODE after main parent config {main_parent}"
                        )

                if self.config["debug"]:
                    print(f"DEBUG    - PARENT0: {parent}, PARENT1: {parent1}, MAIN PARENT: {main_parent}")

                log.debug(f"Before markdown conversion: {markdown}")

                confluence_body = self.confluence_mistune(markdown)

                
                if self.config["debug"]:
                    print(
                        f"\nDEBUG    - UPDATING PAGE TO CONFLUENCE, DETAILS:\n"
                        f"DEBUG    - HOST: {self.config['host_url']}\n"
                        f"DEBUG    - SPACE: {self.config['space']}\n"
                        f"DEBUG    - TITLE: {page.title}\n"
                        f"DEBUG    - PARENT: {parent}\n"
                        f"DEBUG    - BODY: {confluence_body}\n"
                    )

                page_id = self.confluence_api.find_page_id(page.title)
                if page_id:
                    success = self.confluence_api.update_page(page.title, confluence_body)
                    if not success:
                        failed_pages.append((page.title, "Update failed"))
                else:
                    parent_id = self.confluence_api.find_page_id(parent)
                    if not parent_id:
                        # Parent page does not exist, create it under main_parent
                        main_parent_id = self.confluence_api.find_page_id(main_parent)
                        if not main_parent_id:
                            # If main parent also doesn't exist, create it at root (space)
                            main_parent_id = None
                        parent_body = TEMPLATE_BODY.replace("TEMPLATE", parent)
                        created = self.confluence_api.add_page(parent, main_parent_id, parent_body)
                        if created:
                            parent_id = self.confluence_api.find_page_id(parent)
                            log.info(f"Created missing parent page: {parent}")
                        else:
                            failed_pages.append((parent, "Failed to create parent page"))
                            return markdown
                    success = self.confluence_api.add_page(page.title, parent_id, confluence_body)
                    if not success:
                        failed_pages.append((page.title, "Add failed"))
                if page_id is not None:
                    if self.config["debug"]:
                        print(
                            f"DEBUG    - JUST ONE STEP FROM UPDATE OF PAGE '{page.title}' \n"
                            f"DEBUG    - CHECKING IF PARENT PAGE ON CONFLUENCE IS THE SAME AS HERE"
                        )

                    parent_name = self.confluence_api.find_parent_name_of_page(page.title)

                    if parent_name == parent:
                        if self.config["debug"]:
                            print("DEBUG    - Parents match. Continue...")
                    else:
                        if self.config["debug"]:
                            print(f"DEBUG    - ERR, Parents does not match: '{parent}' =/= '{parent_name}' Aborting...")
                        return markdown
                    self.confluence_api.update_page(page.title, confluence_body)
                    for i in MkdocsConfluence.tab_nav:
                        if page.title in i:
                            print(f"INFO    - Mkdocs With Confluence: {i} *UPDATE*")
                else:
                    if self.config["debug"]:
                        print(
                            f"DEBUG    - PAGE: {page.title}, PARENT0: {parent}, "
                            f"PARENT1: {parent1}, MAIN PARENT: {main_parent}"
                        )
                    parent_id = self.confluence_api.find_page_id(parent)
                    self.wait_until(parent_id, 1, 20)
                    second_parent_id = self.confluence_api.find_page_id(parent1)
                    self.wait_until(second_parent_id, 1, 20)
                    main_parent_id = self.confluence_api.find_page_id(main_parent)
                    if not parent_id:
                        if not second_parent_id:
                            main_parent_id = self.confluence_api.find_page_id(main_parent)
                            if not main_parent_id:
                                print("ERR: MAIN PARENT UNKNOWN. ABORTING!")
                                return markdown

                            if self.config["debug"]:
                                print(
                                    f"DEBUG    - Trying to ADD page '{parent1}' to "
                                    f"main parent({main_parent}) ID: {main_parent_id}"
                                )
                            body = TEMPLATE_BODY.replace("TEMPLATE", parent1)
                            self.confluence_api.add_page(parent1, main_parent_id, body)
                            for i in MkdocsConfluence.tab_nav:
                                if parent1 in i:
                                    print(f"INFO    - Mkdocs With Confluence: {i} *NEW PAGE*")
                            time.sleep(1)

                        if self.config["debug"]:
                            print(
                                f"DEBUG    - Trying to ADD page '{parent}' "
                                f"to parent1({parent1}) ID: {second_parent_id}"
                            )
                        body = TEMPLATE_BODY.replace("TEMPLATE", parent)
                        self.confluence_api.add_page(parent, second_parent_id, body)
                        for i in MkdocsConfluence.tab_nav:
                            if parent in i:
                                print(f"INFO    - Mkdocs With Confluence: {i} *NEW PAGE*")
                        time.sleep(1)

                    if parent_id is None:
                        for i in range(11):
                            while parent_id is None:
                                try:
                                    self.confluence_api.add_page(page.title, parent_id, confluence_body)
                                except requests.exceptions.HTTPError:
                                    print(
                                        f"ERR    - HTTP error on adding page. It probably occured due to "
                                        f"parent ID('{parent_id}') page is not YET synced on server. Retry nb {i}/10..."
                                    )
                                    sleep(5)
                                    parent_id = self.confluence_api.find_page_id(parent)
                                break

                    self.confluence_api.add_page(page.title, parent_id, confluence_body)

                    print(f"Trying to ADD page '{page.title}' to parent0({parent}) ID: {parent_id}")
                    for i in MkdocsConfluence.tab_nav:
                        if page.title in i:
                            print(f"INFO    - Mkdocs With Confluence: {i} *NEW PAGE*")
                
                attachments = self.__retrieve_local_images(markdown)
                if attachments:
                    self.page_attachments[page.title] = attachments

            except IndexError as e:
                if self.config["debug"]:
                    print(f"DEBUG    - ERR({e}): Exception error!")
                return markdown
            except Exception as e:
                log.error(f"on_page_markdown: Exception for {page.title}. Error: {e}")
                failed_pages.append((page.title, str(e)))
        # Log failed pages
        if failed_pages:
            log.error("Failed to publish the following pages:")
            for title, error in failed_pages:
                log.error(f"Page: {title}, Error: {error}")

        return markdown

    def __retrieve_local_images(self, markdown):
        attachments = []
        try:
            for match in re.finditer(r'img src="file://(.*)" s', markdown):
                if self.config["debug"]:
                    print(f"DEBUG    - FOUND IMAGE: {match.group(1)}")
                attachments.append(match.group(1))
            for match in re.finditer(r"!\[[\w\. -]*\]\((?!http|file)([^\s,]*).*\)", markdown):
                file_path = match.group(1).lstrip("./\\")
                attachments.append(file_path)

                if self.config["debug"]:
                    print(f"DEBUG    - FOUND IMAGE: {file_path}")
                attachments.append("docs/" + file_path.replace("../", ""))

        except AttributeError as e:
            if self.config["debug"]:
                print(f"DEBUG    - WARN(({e}): No images found in markdown. Proceed..")

        return attachments

    def on_post_page(self, output, page, config):
        site_dir = config.get("site_dir")
        attachments = self.page_attachments.get(page.title, [])

        log.debug("on_post_page: UPLOADING ATTACHMENTS TO CONFLUENCE FOR {page.title}, DETAILS:")
        log.debug("on_post_page: FILES: {attachments}  \n")
            
        for attachment in attachments:
            log.debug("on_post_page: Looking for {attachment} in {site_dir}")   
            for p in Path(site_dir).rglob(f"*{attachment}"):
                self.confluence_api.upsert_attachment(page.title, p)
        return output

    def on_page_content(self, html, page, config, files):
        return html

    def __get_page_url(self, section):
        return re.search("url='(.*)'\\)", section).group(1)[:-1] + ".md"

    def __get_page_name(self, section):
        return os.path.basename(re.search("url='(.*)'\\)", section).group(1)[:-1])

    def __get_section_name(self, section):
        log.debug("SECTION name: {section}")
        return os.path.basename(re.search("url='(.*)'\\/", section).group(1)[:-1])

    def __get_section_title(self, section):
        log.debug("SECTION title: {section}")
        try:
            r = re.search("Section\\(title='(.*)'\\)", section)
            return r.group(1)
        except AttributeError:
            name = self.__get_section_name(section)
            log.warning("Section '{name}' doesn't exist in the mkdocs.yml nav section!")
            return name

    def __get_page_title(self, section):
        try:
            r = re.search("\\s*Page\\(title='(.*)',", section)
            return r.group(1)
        except AttributeError:
            name = self.__get_page_url(section)
            log.warning("Page '{name}' doesn't exist in the mkdocs.yml nav section!")
            return name

    def wait_until(self, condition, interval=0.1, timeout=1):
        start = time.time()
        while not condition and time.time() - start < timeout:
            time.sleep(interval)
            
    def __configure_renderer(self) :
        strip_header = self.config["renderer_options"]["strip_header"]
        log.debug("Configuring renderer with strip_header=%s", strip_header)
        self.confluence_renderer = ConfluenceXhtmlRenderer(strip_header=strip_header)
        self.confluence_mistune = mistune.create_markdown(renderer=self.confluence_renderer, plugins=['table', 'strikethrough', 'task_lists',])
        
    def __configure_http_client(self):
        username = self.config["username"]
        password = self.config["password"]
        if self.config["api_token"]:
            password = (self.config["username"], self.config["api_token"])

        self.confluence_api = ConfluenceAPI(
            self.config["host_url"],
            self.config["space"],
            username,
            password,
            self.dryrun
        )
