import time
import logging

import msal
import requests

from .config import Config

logger = logging.getLogger("recordings-cleanup")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self) -> None:
        self._app = msal.ConfidentialClientApplication(
            client_id=Config.AZURE_CLIENT_ID,
            client_credential=Config.AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{Config.AZURE_TENANT_ID}",
        )
        self._token: dict | None = None
        self._token_expiry: float = 0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token["access_token"]

        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Token acquisition failed: {result.get('error_description', result)}")

        self._token = result
        self._token_expiry = now + result.get("expires_in", 3600)
        logger.debug("Acquired new access token")
        return result["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, url: str) -> None:
        resp = requests.delete(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()

    def _get_paginated(self, url: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        while url:
            data = self._get(url, params=params)
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None  # nextLink already contains query params
        return items

    def get_all_sites(self) -> list[dict]:
        logger.info("Fetching all SharePoint sites")
        sites = self._get_paginated(f"{GRAPH_BASE}/sites?search=*")
        logger.info(f"Found {len(sites)} sites")
        return sites

    def get_site_drives(self, site_id: str) -> list[dict]:
        logger.debug(f"Fetching drives for site {site_id}")
        return self._get_paginated(f"{GRAPH_BASE}/sites/{site_id}/drives")

    def list_drive_items_recursive(self, drive_id: str, folder_path: str = "root") -> list[dict]:
        items: list[dict] = []
        children = self._get_paginated(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_path}/children"
        )
        for child in children:
            if "folder" in child:
                items.extend(self.list_drive_items_recursive(drive_id, child["id"]))
            else:
                items.append(child)
        return items

    def search_drive_items(self, drive_id: str, query: str) -> list[dict]:
        logger.debug(f"Searching drive {drive_id} for '{query}'")
        return self._get_paginated(
            f"{GRAPH_BASE}/drives/{drive_id}/root/search(q='{query}')"
        )

    def delete_item(self, drive_id: str, item_id: str) -> None:
        self._delete(f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}")
