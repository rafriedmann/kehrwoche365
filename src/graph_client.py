import time
import logging

import msal
import requests

from .config import Config

logger = logging.getLogger("recordings-cleanup")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"


class GraphClient:
    def __init__(self) -> None:
        self._app = msal.ConfidentialClientApplication(
            client_id=Config.AZURE_CLIENT_ID,
            client_credential=Config.AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{Config.AZURE_TENANT_ID}",
        )
        self._tokens: dict[str, dict] = {}
        self._token_expiries: dict[str, float] = {}

    def _get_token(self, scope: str = "https://graph.microsoft.com/.default") -> str:
        now = time.time()
        cached = self._tokens.get(scope)
        if cached and now < self._token_expiries.get(scope, 0) - 60:
            return cached["access_token"]

        result = self._app.acquire_token_for_client(scopes=[scope])
        if "access_token" not in result:
            raise RuntimeError(f"Token acquisition failed: {result.get('error_description', result)}")

        self._tokens[scope] = result
        self._token_expiries[scope] = now + result.get("expires_in", 3600)
        logger.debug(f"Acquired new access token for {scope}")
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

    def get_recycle_bin_items(self, site_id: str) -> list[dict]:
        logger.debug(f"Fetching recycle bin for site {site_id}")
        return self._get_paginated(f"{GRAPH_BETA}/sites/{site_id}/recycleBin/items")

    def delete_recycle_bin_item(self, site_id: str, item_id: str) -> None:
        self._delete(f"{GRAPH_BETA}/sites/{site_id}/recycleBin/items/{item_id}")
