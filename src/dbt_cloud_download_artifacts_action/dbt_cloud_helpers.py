import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

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

logger = logging.getLogger(__name__)


class DbtCloudAuth(AuthBase):
    """Create a base object that can be used to authenticate to the dbt Cloud API."""

    def __call__(self, r):
        """Add the authorization header to the request.

        Returns:
            requests.Response: The response from the dbt Cloud API.

        Raises:
            ValueError: If DBT_CLOUD_API_TOKEN is not set.

        """
        token = os.getenv("DBT_CLOUD_API_TOKEN")
        if not token:
            raise ValueError("'DBT_CLOUD_API_TOKEN' environment variable is not set.")
        r.headers["Authorization"] = f"Token {token}"
        return r


@retry(
    reraise=True,
    retry=retry_if_not_exception_type(NonRetryableHTTPError),
    stop=stop_after_delay(30),
    wait=wait_fixed(3),
)
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

    """
    base_url = f"https://{os.getenv('DBT_CLOUD_API_URL_BASE', 'cloud.getdbt.com')}/api/v2/accounts/{account_id}/"
    r = create_requests_session().get(
        auth=DbtCloudAuth(),
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        url=f"{base_url}{endpoint}",
    )
    raise_for_status(r)

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
    # dbt Cloud returns the artifacts of the last step when `step` is omitted.
    params = {"step": step} if step is not None else None
    logger.info("Determining which artifacts are available...")
    r = call_dbt_cloud_api(
        account_id=account_id,
        endpoint=f"runs/{run_id}/artifacts/",
        params=params,
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

        response = call_dbt_cloud_api(
            account_id=account_id,
            endpoint=f"runs/{run_id}/artifacts/{artifact_name}",
            params=params,
        )

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
    artifacts_saved_checks: int = 6,
    max_wait_seconds: int = 1800,
) -> bool:
    """Wait for a dbt Cloud job run to complete and its artifacts to be saved.

    `is_complete` is used rather than `in_progress` as a queued or starting run reports
    `in_progress: false` but has no artifacts yet. Note that a run can report `is_complete` before
    `artifacts_saved`, resulting in an empty list which then errors dbt bouncer.

    Args:
        account_id (int): The dbt Cloud account ID.
        run_id (int): The ID of the dbt Cloud run.
        poll_interval_seconds (int, optional): Seconds between status checks. Defaults to 10.
        artifacts_saved_checks (int, optional): How many status checks of a complete run
            wait for `artifacts_saved` before continuing without it, so a run that never
            saves artifacts does not block. Defaults to 6, so about a minute with current polling configuration.
        max_wait_seconds (int, optional): Maximum seconds to wait for the run to complete. Defaults to 1800.

    Returns:
        bool: True if the run succeeded, False otherwise.

    Raises:
        TimeoutError: If the run does not complete within max_wait_seconds.

    """
    deadline = time.monotonic() + max_wait_seconds
    # Counts only the checks after the run completed, so a long run does not use up
    # the wait for `artifacts_saved`.
    complete_checks = 0
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for dbt Cloud run {run_id} to complete after {max_wait_seconds}s."
            )
        logger.info(f"Checking if run {run_id} is complete...")
        run = call_dbt_cloud_api(account_id=account_id, endpoint=f"runs/{run_id}/")[
            "data"
        ]
        if run["is_complete"]:
            # dbt Cloud can report a run as complete while it is still saving the
            # artifacts. Listing them now returns an empty list, so wait for the save.
            if run["artifacts_saved"]:
                break
            complete_checks += 1
            # Not sure whether dbt turns `artifacts_saved` true on a run
            # that produced no artifacts (for example, when it's canceled or failed before dbt ran). So, to avoid potentially waiting until timeout, we stop waiting after number of checks.
            # In that case we let the download report the empty list.
            if complete_checks >= artifacts_saved_checks:
                logger.warning(
                    f"Run {run_id} is complete, but its artifacts were not saved after {complete_checks} checks. Continuing without them."
                )
                break
            logger.info(
                f"Run {run_id} is complete, waiting {poll_interval_seconds}s for its artifacts to be saved..."
            )
        else:
            logger.info(
                f"Run {run_id} is {run.get('status_humanized', 'not complete')}, waiting {poll_interval_seconds}s..."
            )
        time.sleep(poll_interval_seconds)

    run_status = run["is_success"]
    logger.info(f"Run {run_id} succeeded: {run_status}")

    return run_status
