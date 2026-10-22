import logging
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from requests.auth import AuthBase
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_delay,
    wait_fixed,
)

from dbt_cloud_download_artifacts_action.utils import (
    REQUEST_TIMEOUT_SECONDS,
    NonRetryableHTTPError,
    create_requests_session,
    raise_for_status,
)

# Run URL that dbt Cloud posts as the `target_url` of its commit status, e.g.
# https://cloud.getdbt.com/deploy/<account_id>/projects/<project_id>/runs/<run_id>/
DBT_CLOUD_RUN_URL_PATTERN = re.compile(
    r"/deploy/(?P<account_id>\d+)/projects/\d+/runs/(?P<run_id>\d+)"
)


class GitHubAuth(AuthBase):
    """Base object to use to authenticate to the GitHub API."""

    def __call__(self, r):
        """Add the authorization header to the request.

        Returns:
            requests.Response: The response from the GitHub API.

        Raises:
            ValueError: If neither PAT_GITHUB nor GITHUB_TOKEN is set.

        """
        token = os.getenv("PAT_GITHUB") or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError(
                "Neither 'PAT_GITHUB' nor 'GITHUB_TOKEN' environment variable is set."
            )
        r.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        return r


@retry(
    reraise=True,
    retry=retry_if_not_exception_type(NonRetryableHTTPError),
    stop=stop_after_delay(90),
    wait=wait_fixed(5),
)
def call_github_api(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call the GitHub API with a GET request and return the response as a dictionary.

    Args:
        endpoint (str): The GitHub API endpoint.
        params (Dict, optional): Defaults to None.

    Returns:
        Dict

    """
    r = create_requests_session().get(
        auth=GitHubAuth(),
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        url=f"https://api.github.com/{endpoint}",
    )
    raise_for_status(r)

    logging.debug(f"Response: {r.status_code}, {r.reason}")
    return r.json()


def get_dbt_run_id_per_commit_sha(
    commit_sha: str,
    repo_name: str,
    poll_interval_seconds: int = 5,
    wait_timeout_seconds: int = 120,
) -> tuple[int, int, str]:
    """Get the run ID and host of the dbt Cloud CI job that was triggered by the specified commit.

    Args:
        commit_sha (str): The commit SHA.
        repo_name (str): The full name of the repo, e.g. '<ORG>/<REPO_NAME>'.
        poll_interval_seconds (int, optional): Seconds between status checks. Defaults to 5.
        wait_timeout_seconds (int, optional): Maximum seconds to wait for the dbt Cloud status. Defaults to 120.

    Returns:
        tuple[int, int, str]: The dbt account id, dbt run id, and dbt cloud host associated with the commit_sha.

    Raises:
        RuntimeError: If the dbt Cloud commit status does not link to a run.
        TimeoutError: If no dbt Cloud CI job is found before the timeout expires.
        ValueError: If commit_sha or repo_name is empty.

    """
    if not commit_sha:
        raise ValueError("commit_sha must not be empty.")
    if not repo_name:
        raise ValueError("repo_name must not be empty.")

    deadline = time.monotonic() + wait_timeout_seconds
    latest_check = []
    while True:
        check_info = call_github_api(
            endpoint=f"repos/{repo_name}/commits/{commit_sha}/status"
        )
        logging.debug(f"{check_info=}")
        latest_check = [
            check for check in check_info["statuses"] if check["context"] == "dbt Cloud"
        ]
        logging.debug(f"{latest_check=}")
        if latest_check:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "No dbt Cloud CI job found, has it been triggered correctly?"
            )
        logging.info(f"No dbt Cloud CI job found, waiting {poll_interval_seconds}s...")
        time.sleep(poll_interval_seconds)

    dbt_ci_job_url = latest_check[0]["target_url"]
    match = DBT_CLOUD_RUN_URL_PATTERN.search(dbt_ci_job_url or "")
    if match is None:
        raise RuntimeError(
            f"Could not parse the dbt Cloud account and run id from {dbt_ci_job_url!r}."
        )
    dbt_account_id = int(match["account_id"])
    dbt_run_id = int(match["run_id"])
    parsed_url = urlparse(dbt_ci_job_url)
    dbt_cloud_host = parsed_url.netloc or "cloud.getdbt.com"

    logging.debug(f"{dbt_account_id=}")
    logging.debug(f"{dbt_run_id=}")
    logging.debug(f"{dbt_cloud_host=}")

    return dbt_account_id, dbt_run_id, dbt_cloud_host
