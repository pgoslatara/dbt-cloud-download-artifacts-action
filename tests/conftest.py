from typing import Any, Dict, Generator, Optional

import pytest
import responses
from tenacity import stop_after_delay

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import call_dbt_cloud_api
from dbt_cloud_download_artifacts_action.github_helpers import call_github_api

ACCOUNT_ID = 12893
COMMIT_SHA = "347316746c4c387c1c77bc8a800f524242e619a1"
REPO_NAME = "pgoslatara/dbt-cloud-download-artifacts-action"
RUN_ID = 324231603

DBT_CLOUD_ACCOUNT_URL = f"https://cloud.getdbt.com/api/v2/accounts/{ACCOUNT_ID}"
DBT_CLOUD_RUN_URL = f"{DBT_CLOUD_ACCOUNT_URL}/runs/{RUN_ID}/"
DBT_CLOUD_ARTIFACTS_URL = f"{DBT_CLOUD_RUN_URL}artifacts/"
GITHUB_COMMIT_STATUS_URL = (
    f"https://api.github.com/repos/{REPO_NAME}/commits/{COMMIT_SHA}/status"
)


def dbt_cloud_commit_status() -> Dict[str, Any]:
    """Commit status that dbt Cloud posts to GitHub when it triggers a CI run.

    Returns:
        Dict[str, Any]: The commit status.

    """
    return {
        "context": "dbt Cloud",
        "state": "pending",
        "target_url": f"https://cloud.getdbt.com/deploy/{ACCOUNT_ID}/projects/380303/runs/{RUN_ID}/",
    }


def dbt_cloud_run(
    is_complete: bool,
    in_progress: bool = False,
    is_success: bool = False,
    artifacts_saved: Optional[bool] = None,
) -> Dict[str, Any]:
    """Subset of the dbt Cloud `runs/{id}/` response used by the action.

    Args:
        is_complete (bool): Whether the run is complete.
        in_progress (bool, optional): Whether the run is in progress. Defaults to False.
        is_success (bool, optional): Whether the run succeeded. Defaults to False.
        artifacts_saved (bool, optional): Whether the artifacts are saved. Defaults to `is_complete`.

    Returns:
        Dict[str, Any]: The run response.

    """
    return {
        "data": {
            "artifacts_saved": is_complete
            if artifacts_saved is None
            else artifacts_saved,
            "id": RUN_ID,
            "in_progress": in_progress,
            "is_complete": is_complete,
            "is_success": is_success,
            "status_humanized": "Success" if is_success else "Queued",
        },
        "status": {"is_success": True},
    }


@pytest.fixture(autouse=True)
def no_retries_and_dummy_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.setattr(
        call_github_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.delenv("DBT_CLOUD_API_URL_BASE", raising=False)
    monkeypatch.setenv("DBT_CLOUD_API_TOKEN", "dummy-dbt-cloud-token")
    monkeypatch.setenv("PAT_GITHUB", "dummy-github-token")


@pytest.fixture(autouse=True)
def mocked_responses() -> Generator[responses.RequestsMock, None, None]:
    """Mock all HTTP calls, any unregistered URL raises a `ConnectionError`.

    Yields:
        responses.RequestsMock: The mock to register responses on.

    """
    with responses.RequestsMock() as rsps:
        yield rsps
