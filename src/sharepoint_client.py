import logging

import requests

from .graph_client import GraphClient

logger = logging.getLogger("recordings-cleanup")


class SharePointClient:
    def __init__(self, graph_client: GraphClient) -> None:
        self._graph = graph_client

    def _headers(self) -> dict:
        headers = self._graph._headers()
        headers["Accept"] = "application/json;odata=verbose"
        return headers

    def get_recycle_bin_items(self, site_url: str) -> list[dict]:
        logger.debug(f"Fetching recycle bin for {site_url}")
        items: list[dict] = []
        url = f"{site_url}/_api/web/recyclebin?$orderby=DeletedDate desc&$top=200"
        while url:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("d", {}).get("results", [])
            items.extend(results)
            next_link = data.get("d", {}).get("__next")
            url = next_link if next_link else None
        logger.debug(f"Found {len(items)} recycle bin items in {site_url}")
        return items

    def purge_recycle_bin_item(self, site_url: str, item_id: str) -> None:
        url = f"{site_url}/_api/web/recyclebin('{item_id}')"
        resp = requests.delete(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()

    def get_recording_recycle_items(self, site_url: str) -> list[dict]:
        all_items = self.get_recycle_bin_items(site_url)
        recordings = [
            item for item in all_items
            if item.get("LeafName", "").lower().endswith(".mp4")
        ]
        logger.debug(f"Found {len(recordings)} recording files in recycle bin of {site_url}")
        return recordings
