import logging
from functools import lru_cache

import requests


@lru_cache
def create_requests_session() -> requests.Session:
    """Create a requests session and cache it to avoid recreating the session.

    Returns:
        requests.Session

    """
    logging.info("Creating reusable requests session...")
    return requests.Session()
