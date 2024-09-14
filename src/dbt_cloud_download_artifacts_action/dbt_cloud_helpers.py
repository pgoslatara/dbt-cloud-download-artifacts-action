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
    """Helper function when calling the dbt Cloud API.

    Args:
        account_id (int): The dbt Cloud account ID.
        endpoint (str): The dbt Cloud API endpoint.
        params (Dict, optional): Defaults to None.

    Raises:
        RuntimeError: If the response status code is not 200.

    Returns:
        Dict

    """  # noqa: D401
    base_url = f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/"
    r = create_requests_session().get(
        auth=DbtCloudAuth(),
        params=params,
        url=f"{base_url}{endpoint}",
    )
    try:
        r.raise_for_status()
    except HTTPError as e:
        logging.error(f"{r.status_code=}")
        logging.error(f"{r.content=}")
        raise RuntimeError(e) from e

    logging.debug(f"Response: {r.status_code}, {r.reason}")
    return r.json()


def get_dbt_job_run_artifact(
    account_id: int,
    artifact_name: str,
    output_dir: Path,
    run_id: int,
    step_no: Union[int, None] = None,
) -> None:
    """Get an artifact for a given dbt Cloud run. If specified, save as a file.

    Args:
        account_id (int): The dbt Cloud account ID.
        artifact_name (str): The name of the artifact to download.
        run_id (int): The ID of the dbt Cloud run.
        output_dir (Path): The full path to the directory where files will be saved.
        step_no (int, optional): The step number of the dbt Cloud job. Defaults to None.

    Raises:
        RuntimeError: If the file already exists.


    """
    logging.info(f"Downloading {artifact_name} for run id {run_id}...")

    # Check if file already exists, don't want to overwrite it
    if step_no is None:
        file_name = artifact_name
    else:
        file_name = f'{artifact_name.split(".")[0]}_step_{step_no}.{artifact_name.split(".")[-1]}'

    artifact_file_path = output_dir / file_name
    if artifact_file_path.exists():
        raise RuntimeError(
            f"File {artifact_file_path} already exists, cancelling download."
        )

    endpoint = f"runs/{run_id}/artifacts/{artifact_name}"
    if step_no is not None:
        endpoint += f"?step={step_no}"

    response = call_dbt_cloud_api(account_id=account_id, endpoint=endpoint)

    Path.mkdir(Path(output_dir / artifact_name).parent, exist_ok=True, parents=True)
    logging.info(
        f"Saving {artifact_name} for run id {run_id} to {artifact_file_path}..."
    )
    with Path.open(output_dir / file_name, "w") as outfile:
        json.dump(response, outfile)


def wait_for_dbt_cloud_job_status(
    account_id: int,
    run_id: int,
) -> None:
    """Wait for a dbt Cloud job to complete."""
    in_progress = True
    while in_progress:
        logging.info(f"Run {run_id} is in progress...")
        in_progress = call_dbt_cloud_api(
            account_id=account_id, endpoint=f"runs/{run_id}/"
        )["data"]["in_progress"]
        time.sleep(10)

    run_status = call_dbt_cloud_api(account_id=account_id, endpoint=f"runs/{run_id}/")[
        "data"
    ]["is_success"]
    logging.info(f"Run {run_id} succeeded: {run_status}")

    return run_status
