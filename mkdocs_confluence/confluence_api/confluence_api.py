import hashlib
import mimetypes
import os
from pathlib import Path
import re
import requests
from mkdocs.plugins import get_plugin_logger
import time

from mkdocs_confluence.config.mkdocs_confluence_config import nostdout

log = get_plugin_logger(__name__)

class ConfluenceAPI:
    def __init__(self, base_url: str, space: str, username: str, password: str, dryrun: bool = False):
        self.base_url = base_url
        self.space = space
        self.auth = (username, password)
        self.dryrun = dryrun
        self.page_link_map = {}
        self.representation = "storage"  # Always use storage format for modern editor
        

    def upsert_attachment(self, page_name, filepath):
        log.info(f"upsert_attachment:  {page_name} *ADD/Update ATTACHMENT if required* {filepath}")
        log.debug("upsert_attachment: PAGE NAME: {page_name}, FILE: {filepath}")
        page_id = self.find_page_id(page_name)
        if page_id:
            file_hash = self.get_file_sha1(filepath)
            attachment_message = f"MkdocsConfluence [v{file_hash}]"
            existing_attachment = self.get_attachment(page_id, filepath)
            if existing_attachment:
                file_hash_regex = re.compile(r"\[v([a-f0-9]{40})]$")
                existing_match = file_hash_regex.search(existing_attachment["version"]["message"])
                if existing_match is not None and existing_match.group(1) == file_hash:
                    log.debug(f"upsert_attachment: * {page_name} * Existing attachment skipping * {filepath}")
                else:
                    self.update_attachment(page_id, filepath, existing_attachment, attachment_message)
            else:
                self.create_attachment(page_id, filepath, attachment_message)
        else:
            log.debug("upsert_attachment: PAGE DOES NOT EXISTS")
                
    def get_attachment(self, page_id, filepath):
        name = os.path.basename(filepath)
        log.debug(f" * Mkdocs With Confluence: Get Attachment: PAGE ID: {page_id}, FILE: {filepath}")

        url = self.base_url + "/" + page_id + "/child/attachment"
        headers = {"X-Atlassian-Token": "no-check"}  # no content-type here!
        log.debug(f"get_attachment URL: {url}")

        r = requests.get(url, headers=headers, params={"filename": name, "expand": "version"}, auth=self.auth)
        r.raise_for_status()
        with nostdout():
            response_json = r.json()
        if response_json["size"]:
            return response_json["results"][0]

    def update_attachment(self, page_id, filepath, existing_attachment, message):
        log.debug(f"update_attachment: Update Attachment: PAGE ID: {page_id}, FILE: {filepath}")

        url = self.base_url + "/" + page_id + "/child/attachment/" + existing_attachment["id"] + "/data"
        headers = {"X-Atlassian-Token": "no-check"}  # no content-type here!

        log.debug(f"update_attachment: URL: {url}")

        filename = os.path.basename(filepath)

        # determine content-type
        content_type, encoding = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = "multipart/form-data"
        files = {"file": (filename, open(Path(filepath), "rb"), content_type)}
        data = {"comment": message}

        if not self.dryrun:
            r = requests.post(url, headers=headers, files=files, data=data, auth=self.auth)
            r.raise_for_status()
            log.info(r.json())
            if r.status_code == 200:
                log.info("OK!")
            else:
                log.info("ERR!")

    def create_attachment(self, page_id, filepath, message):
        log.debug(f"create_attachment: Create Attachment: PAGE ID: {page_id}, FILE: {filepath}")

        url = self.base_url + "/" + page_id + "/child/attachment"
        headers = {"X-Atlassian-Token": "no-check"}  # no content-type here!

        log.debug(f"create_attachment: URL: {url}")

        filename = os.path.basename(filepath)

        # determine content-type
        content_type, encoding = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = "multipart/form-data"
        files = {"file": (filename, open(filepath, "rb"), content_type)}
        data = {"comment": message}
        if not self.dryrun:
            r = requests.post(url, headers=headers, files=files, data=data, auth=self.auth)
            log.info(r.json())
            r.raise_for_status()
            if r.status_code == 200:
                log.info("OK!")
            else:
                log.info("ERR!")
                
    def find_page_id(self, page_name, parent_id=None):
        if page_name is None:
            return None
        log.debug(f"Find Page ID: PAGE NAME: {page_name}")
        name_confl = page_name.replace(" ", "+")
        url = self.base_url + "?title=" + name_confl + "&spaceKey=" + self.space + "&expand=ancestors"
        log.debug(f"find_page_id URL: {url}")
        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        with nostdout():
            response_json = response.json()
        for result in response_json.get("results", []):
            if parent_id is None:
                return result["id"]
            ancestors = result.get("ancestors", [])
            if ancestors and str(ancestors[-1]["id"]) == str(parent_id):
                return result["id"]
        log.debug("PAGE DOES NOT EXIST under the specified parent")
        return None
        
    def find_parent_name_of_page(self, name):
        log.debug(f"find_parent_name_of_page: Find PARENT OF PAGE, PAGE NAME: {name}")
        idp = self.find_page_id(name)
        url = self.base_url + "/" + idp + "?expand=ancestors"

        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        with nostdout():
            response_json = response.json()
        if response_json:
            log.debug(f"find_parent_name_of_page: PARENT NAME: {response_json['ancestors'][-1]['title']}")
            return response_json["ancestors"][-1]["title"]
        else:
            log.debug("find_parent_name_of_page: PAGE DOES NOT HAVE PARENT")
            return None
    
    def get_file_sha1(self, file_path):
        hash_sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
        return hash_sha1.hexdigest()
    
    def add_page(self, page_name, parent_page_id, page_content_in_storage_format):
        log.info(f"add_page: {page_name} - *NEW PAGE*")
        url = self.base_url + "/"
        headers = {"Content-Type": "application/json"}
        data = {
            "type": "page",
            "title": page_name,
            "space": {"key": self.space},
            "body": {"storage": {"value": page_content_in_storage_format, "representation": self.representation}},
        }
        if parent_page_id:
            data["ancestors"] = [{"id": parent_page_id}]
        # else: do not include ancestors at all

        try:
            if not self.dryrun:
                response = requests.post(url, json=data, headers=headers, auth=self.auth)
                response.raise_for_status()
                if response.status_code == 200:
                    log.info("add_page: OK Successfully added page")
                    # Print the final Confluence link
                    page_id = response.json().get("id")
                    if page_id:
                        # Remove /rest/api/content/ from base_url to get the site root
                        site_root = self.base_url.split("/rest/api/content")[0]
                        page_url = f"{site_root}/pages/viewpage.action?pageId={page_id}"
                        log.info(f"Confluence page published: {page_url}")
                        # --- Store mapping for internal links ---
                        if not hasattr(self, 'page_link_map'):
                            self.page_link_map = {}
                        self.page_link_map[page_name] = page_url
                        print(f"DEBUG: Published page mapping: {page_name} -> {page_url}")
                        print(f"DEBUG: Current page link map: {self.page_link_map}")
                    return True
        except Exception as e:
            return False

        log.error(f"add_page: Failed to add page {page_name}.")
        return False

    def update_page(self, page_name, page_content_in_storage_format):
        page_id = self.find_page_id(page_name)
        if not page_id:
            log.error(f"update_page: PAGE DOES NOT EXIST for {page_name}")
            return False

        log.info(f"update_page: {page_name} - *UPDATE*")
        url = self.base_url + "/" + page_id
        headers = {"Content-Type": "application/json"}
        page_version = self.find_page_version(page_name) + 1
        data = {
            "id": page_id,
            "title": page_name,
            "type": "page",
            "space": {"key": self.space},
            "body": {"storage": {"value": page_content_in_storage_format, "representation": self.representation}},
            "version": {"number": page_version},
        }

        try:
            if not self.dryrun:
                response = requests.put(url, json=data, headers=headers, auth=self.auth)
                response.raise_for_status()
                if response.status_code == 200:
                    log.info("update_page: OK Successfully updated page")
                    # Print the final Confluence link
                    page_id = response.json().get("id")
                    if page_id:
                        site_root = self.base_url.split("/rest/api/content")[0]
                        page_url = f"{site_root}/pages/viewpage.action?pageId={page_id}"
                        log.info(f"Confluence page published: {page_url}")
                        # --- Store mapping for internal links ---
                        if not hasattr(self, 'page_link_map'):
                            self.page_link_map = {}
                        self.page_link_map[page_name] = page_url
                        print(f"DEBUG: Published page mapping: {page_name} -> {page_url}")
                        print(f"DEBUG: Current page link map: {self.page_link_map}")
                    return True
        except Exception as e:
            #log.error(f"update_page: Failed to update page {page_name}. Error: {e}")
            return False

        log.error(f"update_page: Failed to update page {page_name}.")
        return False
                    
    def find_page_version(self, page_name):
        log.debug(f"find_page_version: Find PAGE VERSION, PAGE NAME: {page_name}")
        name_confl = page_name.replace(" ", "+")
        url = self.base_url + "?title=" + name_confl + "&spaceKey=" + self.space + "&expand=version"
        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        with nostdout():
            response_json = response.json()
        if response_json["results"] is not None:
            log.debug(f"find_page_version: VERSION: {response_json['results'][0]['version']['number']}")
            return response_json["results"][0]["version"]["number"]
        else:
            log.debug("find_page_version: PAGE DOES NOT EXIST")
            return None

    def find_parent_name_of_page(self, name):
        log.debug(f"find_parent_name_of_page: Find PARENT OF PAGE, PAGE NAME: {name}")
        idp = self.find_page_id(name)
        url = self.base_url + "/" + idp + "?expand=ancestors"

        response = requests.get(url, auth=self.auth)
        response.raise_for_status()
        with nostdout():
            response_json = response.json()
        if response_json:
            log.debug(f"find_parent_name_of_page: PARENT NAME: {response_json['ancestors'][-1]['title']}")
            return response_json["ancestors"][-1]["title"]
        else:
            log.debug("find_parent_name_of_page: PAGE DOES NOT HAVE PARENT")
            return None