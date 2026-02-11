import logging
from datetime import datetime, timezone, timedelta

import requests

from .config import Config
from .graph_client import GraphClient

logger = logging.getLogger("recordings-cleanup")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def run_cleanup() -> dict:
    graph = GraphClient()
    cutoff = datetime.now(timezone.utc) - timedelta(days=Config.RETENTION_DAYS)
    dry_run = Config.DRY_RUN

    stats = {"files_deleted": 0, "bytes_freed": 0, "first_stage_purged": 0, "second_stage_purged": 0, "errors": 0}

    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"Starting cleanup [{mode}] - retention={Config.RETENTION_DAYS}d, cutoff={cutoff.isoformat()}")

    # Step 1: Get all sites
    try:
        sites = graph.get_all_sites()
    except Exception:
        logger.exception("Failed to fetch sites")
        return stats

    for site in sites:
        site_id = site["id"]
        site_name = site.get("displayName", site_id)
        site_url = site.get("webUrl", "")
        logger.info(f"Processing site: {site_name} ({site_url})")

        # Step 2: Get drives for each site
        try:
            drives = graph.get_site_drives(site_id)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404):
                logger.debug(f"Skipping site {site_name} (no access)")
            else:
                logger.warning(f"Failed to fetch drives for site {site_name}: {e}")
                stats["errors"] += 1
            continue

        for drive in drives:
            drive_id = drive["id"]
            drive_name = drive.get("name", drive_id)
            logger.debug(f"  Searching drive: {drive_name}")

            # Step 3: Search for .mp4 files
            try:
                items = graph.search_drive_items(drive_id, ".mp4")
            except Exception:
                logger.exception(f"Failed to search drive {drive_name} in site {site_name}")
                stats["errors"] += 1
                continue

            for item in items:
                name = item.get("name", "")
                if not name.lower().endswith(".mp4"):
                    continue

                # Only delete recordings from the Recordings folder
                parent_path = item.get("parentReference", {}).get("path", "")
                if "/Recordings" not in parent_path:
                    logger.debug(f"  Skipping {name} (not in Recordings folder: {parent_path})")
                    continue

                created = _parse_datetime(item.get("createdDateTime", ""))
                size = item.get("size", 0)
                age_days = (datetime.now(timezone.utc) - created).days

                if created >= cutoff:
                    continue

                logger.info(
                    f"  {'[DRY RUN] Would delete' if dry_run else 'Deleting'}: "
                    f"{name} (size={_format_size(size)}, age={age_days}d, site={site_name})"
                )

                if not dry_run:
                    try:
                        graph.delete_item(drive_id, item["id"])
                        stats["files_deleted"] += 1
                        stats["bytes_freed"] += size
                    except Exception:
                        logger.exception(f"Failed to delete {name}")
                        stats["errors"] += 1
                else:
                    stats["files_deleted"] += 1
                    stats["bytes_freed"] += size

        # Step 4: Optionally purge 1st stage recycle bin
        if Config.PURGE_FIRST_STAGE:
            try:
                recycle_items = graph.get_recycle_bin_items(site_id)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (403, 404):
                    logger.debug(f"Skipping 1st stage recycle bin for {site_name} (no access)")
                else:
                    logger.warning(f"Failed to fetch 1st stage recycle bin for {site_name}: {e}")
                    stats["errors"] += 1
                recycle_items = []

            for ritem in recycle_items:
                name = ritem.get("name", "")
                if not name.lower().endswith(".mp4"):
                    continue

                item_id = ritem.get("id", "")
                size = ritem.get("size", 0)

                deleted_str = ritem.get("deletedDateTime", "")
                if deleted_str:
                    try:
                        deleted_date = _parse_datetime(deleted_str)
                        if deleted_date >= cutoff:
                            logger.debug(f"  Skipping 1st stage item (too recent): {name}")
                            continue
                    except Exception:
                        logger.warning(f"  Could not parse deletedDateTime for {name}, skipping")
                        continue

                logger.info(
                    f"  {'[DRY RUN] Would purge' if dry_run else 'Purging'} from 1st stage: "
                    f"{name} (size={_format_size(size)}, site={site_name})"
                )

                if not dry_run:
                    try:
                        graph.permanent_delete_recycle_bin_item(site_id, item_id)
                        stats["first_stage_purged"] += 1
                    except Exception:
                        logger.exception(f"Failed to purge {name} from 1st stage")
                        stats["errors"] += 1
                else:
                    stats["first_stage_purged"] += 1

        # Step 5: Always purge 2nd stage recycle bin
        if not site_url:
            continue

        try:
            second_stage_items = graph.get_second_stage_recycle_bin(site_url)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403, 404):
                logger.debug(f"Skipping 2nd stage recycle bin for {site_name} (no access)")
            else:
                logger.warning(f"Failed to fetch 2nd stage recycle bin for {site_name}: {e}")
                stats["errors"] += 1
            continue

        for ritem in second_stage_items:
            leaf_name = ritem.get("LeafName", "")
            if not leaf_name.lower().endswith(".mp4"):
                continue

            item_id = ritem.get("Id", "")
            size = ritem.get("Size", 0)

            deleted_date_str = ritem.get("DeletedDate", "")
            if deleted_date_str:
                try:
                    deleted_date = _parse_datetime(deleted_date_str)
                    if deleted_date >= cutoff:
                        logger.debug(f"  Skipping 2nd stage item (too recent): {leaf_name}")
                        continue
                except Exception:
                    logger.warning(f"  Could not parse DeletedDate for {leaf_name}, skipping")
                    continue

            logger.info(
                f"  {'[DRY RUN] Would purge' if dry_run else 'Purging'} from 2nd stage: "
                f"{leaf_name} (size={_format_size(size)}, site={site_name})"
            )

            if not dry_run:
                try:
                    graph.purge_second_stage_item(site_url, item_id)
                    stats["second_stage_purged"] += 1
                except Exception:
                    logger.exception(f"Failed to purge {leaf_name} from 2nd stage")
                    stats["errors"] += 1
            else:
                stats["second_stage_purged"] += 1

    logger.info(
        f"Cleanup complete [{mode}]: "
        f"files_deleted={stats['files_deleted']}, "
        f"bytes_freed={_format_size(stats['bytes_freed'])}, "
        f"first_stage_purged={stats['first_stage_purged']}, "
        f"second_stage_purged={stats['second_stage_purged']}, "
        f"errors={stats['errors']}"
    )
    return stats
