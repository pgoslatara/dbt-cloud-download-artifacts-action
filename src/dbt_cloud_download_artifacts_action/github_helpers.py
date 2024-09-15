import logging
import os
import time
from typing import Any, Dict, Optional

from requests import HTTPError
from requests.auth import AuthBase
from requests.structures import CaseInsensitiveDict
from tenacity import retry, stop_after_delay, wait_fixed
from wrapt_timeout_decorator import timeout

from dbt_cloud_download_artifacts_action.utils import create_requests_session


class GitHubAuth(AuthBase):
    """Base object to use to authenticate to the GitHub API."""

    def __call__(self, r):
        """Add the authorization header to the request.

        Returns:
            requests.Response: The response from the GitHub API.

        """
        r.headers = CaseInsensitiveDict(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {os.getenv('PAT_GITHUB')}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        return r


@retry(stop=stop_after_delay(90), wait=wait_fixed(5))
def call_github_api(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call the GitHub API with a GET request and return the response as a dictionary.

    Args:
        endpoint (str): The GitHub API endpoint.
        params (Dict, optional): Defaults to None.

    Raises:
        RuntimeError: If the response status code is not 200.

    Returns:
        Dict

    """
    r = create_requests_session().get(
        auth=GitHubAuth(),
        params=params,
        url=f"https://api.github.com/{endpoint}",
    )

    try:
        r.raise_for_status()
    except HTTPError as e:
        logging.error(f"{r.status_code=}")
        logging.error(f"{r.content=}")
        raise RuntimeError(e) from e

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
    dbt_account_id = int(dbt_ci_job_url.split("/")[-6])
    dbt_run_id = int(dbt_ci_job_url.split("/")[-2])

    logging.debug(f"{dbt_account_id=}")
    logging.debug(f"{dbt_run_id=}")

    return dbt_account_id, dbt_run_id
