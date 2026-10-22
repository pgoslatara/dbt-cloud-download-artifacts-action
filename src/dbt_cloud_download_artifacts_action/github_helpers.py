import logging
import os
import re
import time
from typing import Any, Dict, Optional

from requests.auth import AuthBase
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_delay,
    wait_fixed,
)
from wrapt_timeout_decorator import timeout

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

        """
        r.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {os.getenv('PAT_GITHUB')}",
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


@timeout(
    30,
    exception_message="No dbt Cloud CI job found, has it been triggered correctly?",
    use_signals=True,
)
def get_dbt_run_id_per_commit_sha(commit_sha: str, repo_name: str) -> tuple[int, int]:
    """Get the run ID of the dbt Cloud CI job that was triggered by the specified commit.

    Args:
        commit_sha (str): The commit SHA.
        repo_name (str): The full name of the repo, e.g. '<ORG>/<REPO_NAME>'.

    Returns:
        tuple(int, int): The dbt account id and dbt run id associated with the commit_sha.

    Raises:
        RuntimeError: If the dbt Cloud commit status does not link to a run.

    """
    # Using a `while` loop to allow for a (short) delay between the commit being pushed and the dbt Cloud CI job starting.
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
        if latest_check != []:
            break
        logging.info("No dbt Cloud CI job found, waiting 5s...")
        time.sleep(5)

    dbt_ci_job_url = latest_check[0]["target_url"]
    match = DBT_CLOUD_RUN_URL_PATTERN.search(dbt_ci_job_url or "")
    if match is None:
        raise RuntimeError(
            f"Could not parse the dbt Cloud account and run id from {dbt_ci_job_url!r}."
        )
    dbt_account_id = int(match["account_id"])
    dbt_run_id = int(match["run_id"])

    logging.debug(f"{dbt_account_id=}")
    logging.debug(f"{dbt_run_id=}")

    return dbt_account_id, dbt_run_id
