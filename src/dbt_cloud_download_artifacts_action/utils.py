import logging
from functools import lru_cache

import requests
from requests import HTTPError

# Seconds to wait for the server to connect or send data before the request fails.
REQUEST_TIMEOUT_SECONDS = 30

# Client errors that can succeed on a later attempt, e.g. rate limiting.
RETRYABLE_CLIENT_ERROR_STATUS_CODES = {408, 429}


class NonRetryableHTTPError(RuntimeError):
    """An HTTP error that will not succeed on retry, e.g. an invalid token or endpoint."""


@lru_cache
def create_requests_session() -> requests.Session:
    """Create a requests session and cache it to avoid recreating the session.

    Returns:
        requests.Session

    """
    logging.info("Creating reusable requests session...")
    return requests.Session()


def raise_for_status(response: requests.Response) -> None:
    """Raise an error if the response was not successful.

    Args:
        response (requests.Response): The response to check.

    Raises:
        NonRetryableHTTPError: If the response is a client error that a retry cannot fix.
        RuntimeError: If the response is any other error.

    """
    try:
        response.raise_for_status()
    except HTTPError as e:
        logging.error(f"{response.status_code=}")
        logging.error(f"{response.content=}")
        if (
            400 <= response.status_code < 500
            and response.status_code not in RETRYABLE_CLIENT_ERROR_STATUS_CODES
        ):
            raise NonRetryableHTTPError(e) from e
        raise RuntimeError(e) from e
