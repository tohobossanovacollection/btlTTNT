import logging
import sys

from app.utils.request_context import RequestIdFilter


def configure_logging(level: str) -> None:
    normalized = str(level or "").strip().upper() or "INFO"
    logging.basicConfig(
        level=normalized,
        format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    request_filter = RequestIdFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(request_filter)

