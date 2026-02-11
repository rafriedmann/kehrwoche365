import signal
import sys
import logging
import time

from croniter import croniter
from datetime import datetime, timezone

from .config import Config, setup_logging
from .cleanup import run_cleanup

logger: logging.Logger | None = None
_shutdown = False


def _handle_signal(signum: int, _frame) -> None:
    global _shutdown
    sig_name = signal.Signals(signum).name
    if logger:
        logger.info(f"Received {sig_name}, shutting down gracefully...")
    _shutdown = True


def main() -> None:
    global logger
    logger = setup_logging()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(f"Teams Recordings Cleanup starting")
    logger.info(f"  Domain:    {Config.SHAREPOINT_DOMAIN}")
    logger.info(f"  Retention: {Config.RETENTION_DAYS} days")
    logger.info(f"  Dry Run:   {Config.DRY_RUN}")
    logger.info(f"  Schedule:  {Config.CRON_SCHEDULE}")

    # Run once immediately
    logger.info("Running initial cleanup...")
    run_cleanup()

    if _shutdown:
        logger.info("Shutdown requested, exiting")
        return

    # Then schedule via cron
    logger.info(f"Scheduling next runs with cron: {Config.CRON_SCHEDULE}")
    cron = croniter(Config.CRON_SCHEDULE, datetime.now(timezone.utc))

    while not _shutdown:
        next_run = cron.get_next(datetime)
        logger.info(f"Next run scheduled at {next_run.isoformat()}")

        while not _shutdown:
            now = datetime.now(timezone.utc)
            if now >= next_run:
                break
            time.sleep(min(30, (next_run - now).total_seconds()))

        if _shutdown:
            break

        logger.info("Scheduled cleanup starting...")
        run_cleanup()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
