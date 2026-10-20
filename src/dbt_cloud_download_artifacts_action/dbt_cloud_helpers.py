import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from requests import HTTPError
from requests.auth import AuthBase
from requests.structures import CaseInsensitiveDict
from tenacity import retry, stop_after_delay, wait_fixed

from dbt_cloud_download_artifacts_action.utils import create_requests_session

logger = logging.getLogger(__name__)


class DbtCloudAuth(AuthBase):
    """Create a base object that can be used to authenticate to the dbt Cloud API."""

    def __call__(self, r):
        """Add the authorization header to the request.

        Returns:
            requests.Response: The response from the dbt Cloud API.

        """
        r.headers = CaseInsensitiveDict(
            {
                "Authorization": f"Token {os.getenv('DBT_CLOUD_API_TOKEN')}",
            }
        )
        return r


@retry(stop=stop_after_delay(30), wait=wait_fixed(3))
def call_dbt_cloud_api(
    account_id: int,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call the dbt Cloud API with a GET request and return the response as a dictionary.

    Args:
        account_id (int): The dbt Cloud account ID.
        endpoint (str): The dbt Cloud API endpoint.
        params (Dict, optional): Defaults to None.

    Returns:
        Dict

    Raises:
        RuntimeError: If the response status code is not 200.

    """
    base_url = f"https://{os.getenv('DBT_CLOUD_API_URL_BASE', 'cloud.getdbt.com')}/api/v2/accounts/{account_id}/"
    r = create_requests_session().get(
        auth=DbtCloudAuth(),
        params=params,
        url=f"{base_url}{endpoint}",
    )
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error(f"{r.status_code=}")
        logger.error(f"{r.content=}")
        raise RuntimeError(e) from e

    logger.debug(f"Response: {r.status_code}, {r.reason}")
    return r.json()


def get_dbt_job_run_artifacts(
    account_id: int,
    output_dir: Path,
    run_id: int,
    step: Union[int, None] = None,
) -> None:
    """Get the artifacts for a given dbt Cloud run and save as a file.

    Args:
        account_id (int): The dbt Cloud account ID.
        run_id (int): The ID of the dbt Cloud run.
        output_dir (Path): The full path to the directory where files will be saved.
        step (int, optional): The step number of the dbt Cloud job. Defaults to None, will download from the last step.

    Raises:
        FileExistsError: If the file already exists.
        RuntimeError: If the run has no artifacts.

    """
    logger.info("Determining which artifacts are available...")
    r = call_dbt_cloud_api(
        account_id=account_id,
        endpoint=f"runs/{run_id}/artifacts/",
    )
    if not r["data"]:
        raise RuntimeError(
            f"dbt Cloud run {run_id} has no artifacts, did the run produce any?"
        )
    json_artifacts = [x for x in r["data"] if x.endswith(".json")]
    logger.debug(f"{json_artifacts=}")
    for artifact_name in json_artifacts:
        logger.info(f"Downloading {artifact_name} for run id {run_id}...")

        artifact_file_path = output_dir / artifact_name
        if artifact_file_path.exists():
            raise FileExistsError(
                f"File {artifact_file_path} already exists, cancelling download."
            )

        endpoint = f"runs/{run_id}/artifacts/{artifact_name}"
        if step is not None:
            endpoint += f"?step={step}"

        response = call_dbt_cloud_api(account_id=account_id, endpoint=endpoint)

        Path.mkdir(Path(artifact_file_path).parent, exist_ok=True, parents=True)
        logger.info(
            f"Saving {artifact_name} for run id {run_id} to {artifact_file_path}..."
        )
        with Path.open(artifact_file_path, "w") as outfile:
            json.dump(response, outfile)


def wait_for_dbt_cloud_job_run_status(
    account_id: int,
    run_id: int,
    poll_interval_seconds: int = 10,
) -> bool:
    """Wait for a dbt Cloud job run to complete.

    `is_complete` is used rather than `in_progress` as a queued or starting run reports
    `in_progress: false` but has no artifacts yet.

    Args:
        account_id (int): The dbt Cloud account ID.
        run_id (int): The ID of the dbt Cloud run.
        poll_interval_seconds (int, optional): Seconds between status checks. Defaults to 10.

    Returns:
        bool: True if the run succeeded, False otherwise.

    """
    while True:
        logger.info(f"Checking if run {run_id} is complete...")
        run = call_dbt_cloud_api(account_id=account_id, endpoint=f"runs/{run_id}/")[
            "data"
        ]
        if run["is_complete"]:
            break
        logger.info(
            f"Run {run_id} is {run.get('status_humanized', 'not complete')}, waiting {poll_interval_seconds}s..."
        )
        time.sleep(poll_interval_seconds)

    run_status = run["is_success"]
    logger.info(f"Run {run_id} succeeded: {run_status}")

    return run_status
