import os
import logging

from dotenv import load_dotenv

load_dotenv()


class Config:
    AZURE_TENANT_ID: str = os.environ["AZURE_TENANT_ID"]
    AZURE_CLIENT_ID: str = os.environ["AZURE_CLIENT_ID"]
    AZURE_CLIENT_SECRET: str = os.environ["AZURE_CLIENT_SECRET"]

    SHAREPOINT_DOMAIN: str = os.getenv("SHAREPOINT_DOMAIN", "partnereifer.sharepoint.com")
    RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "8"))
    CRON_SCHEDULE: str = os.getenv("CRON_SCHEDULE", "0 2 * * *")
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
    PURGE_FIRST_STAGE: bool = os.getenv("PURGE_FIRST_STAGE", "false").lower() in ("true", "1", "yes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


def setup_logging(level: str = Config.LOG_LEVEL) -> logging.Logger:
    logger = logging.getLogger("recordings-cleanup")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
        ))
        logger.addHandler(handler)

    return logger
