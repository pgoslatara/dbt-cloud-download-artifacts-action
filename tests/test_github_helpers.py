import os

import pytest
from tenacity import RetryError, stop_after_delay

from dbt_cloud_download_artifacts_action.github_helpers import (
    call_github_api,
    get_dbt_run_id_per_commit_sha,
)
from dbt_cloud_download_artifacts_action.logger import logging


def test_get_dbt_run_id_per_commit_sha(monkeypatch):
    """Test that the dbt Cloud run id can be retrieved for a commit sha."""
    monkeypatch.setattr(call_github_api.retry, "stop", stop_after_delay(0))
    r = get_dbt_run_id_per_commit_sha(
        commit_sha=os.getenv("COMMIT_SHA"),
        repo_name=os.getenv("REPO_NAME"),
    )
    assert r == (int(os.getenv("DBT_ACCOUNT_ID")), int(os.getenv("DBT_RUN_ID")))  # type: ignore[arg-type]


def test_github_api_connection(monkeypatch):
    """Test that the GitHub API can be reached"""
    monkeypatch.setattr(call_github_api.retry, "stop", stop_after_delay(0))
    response = call_github_api(
        endpoint="user",  # Unfortunately this endpoint doesn't return a `success` key,
    )
    logging.warning(response)
    assert isinstance(response["id"], int)


def test_github_api_connection_nonexisting_endpoint(monkeypatch):
    """Test that the GitHub API can be reached."""
    monkeypatch.setattr(call_github_api.retry, "stop", stop_after_delay(0))
    with pytest.raises(RetryError):
        call_github_api(endpoint="I_don_t_exist")
