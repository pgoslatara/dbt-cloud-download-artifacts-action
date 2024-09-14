import logging
from contextlib import contextmanager
from typing import Generator, List, Tuple

from _pytest.logging import LogCaptureHandler


# Source: https://github.com/pytest-dev/pytest/issues/3697#issuecomment-792129636
@contextmanager
def catch_logs() -> Generator[LogCaptureHandler, None, None]:
    """Context manager that sets the level for capturing of logs.

    After the end of the 'with' statement the level is restored to its original value.

    Yields:
        LogCaptureHandler: The log capture handler.

    """
    handler = LogCaptureHandler()
    logger = logging.getLogger("")
    orig_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.setLevel(orig_level)
        logger.removeHandler(handler)


def records_to_tuples(records: List[logging.LogRecord]) -> List[Tuple[str, int, str]]:
    """List of stripped down log records intended for use in assertion comparison.

    Args:
        records: The log records.

    Returns:
        A list of tuples of the form (name, level, message).

    """
    return [(r.name, r.levelno, r.getMessage()) for r in records]
