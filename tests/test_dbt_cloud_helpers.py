import json
import logging
from pathlib import Path

import pytest
from responses import matchers
from tenacity import stop_after_attempt, wait_fixed

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    call_dbt_cloud_api,
    get_dbt_job_run_artifacts,
    wait_for_dbt_cloud_job_run_status,
)
from dbt_cloud_download_artifacts_action.utils import NonRetryableHTTPError

from .conftest import (
    ACCOUNT_ID,
    DBT_CLOUD_ACCOUNT_URL,
    DBT_CLOUD_ARTIFACTS_URL,
    DBT_CLOUD_RUN_URL,
    RUN_ID,
    dbt_cloud_run,
)

MANIFEST = {"metadata": {"dbt_schema_version": "manifest/v12"}}


def test_dbt_cloud_api_connection(mocked_responses):
    """Test that the dbt Cloud API is called with the token."""
    mocked_responses.get(
        f"{DBT_CLOUD_ACCOUNT_URL}/projects/",
        json={"data": [], "status": {"is_success": True}},
        match=[
            matchers.header_matcher({"Authorization": "Token dummy-dbt-cloud-token"})
        ],
    )
    response = call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="projects/")
    assert response["status"]["is_success"]


def test_dbt_cloud_api_custom_url_base(mocked_responses, monkeypatch):
    """Test that `DBT_CLOUD_API_URL_BASE` overrides the default host."""
    monkeypatch.setenv("DBT_CLOUD_API_URL_BASE", "ab123.us1.dbt.com")
    mocked_responses.get(
        f"https://ab123.us1.dbt.com/api/v2/accounts/{ACCOUNT_ID}/projects/",
        json={"data": [], "status": {"is_success": True}},
    )
    response = call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="projects/")
    assert response["status"]["is_success"]


def test_dbt_cloud_api_client_error_not_retried(mocked_responses, monkeypatch):
    """Test that an invalid endpoint fails on the first attempt."""
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_attempt(3),
    )
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "wait",
        wait_fixed(0),
    )
    mocked_responses.get(f"{DBT_CLOUD_ACCOUNT_URL}/non_existent_endpoint/", status=404)

    with pytest.raises(NonRetryableHTTPError, match="404"):
        call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="non_existent_endpoint/")

    assert len(mocked_responses.calls) == 1


@pytest.mark.parametrize("status", [429, 500, 503])
def test_dbt_cloud_api_transient_error_retried(mocked_responses, monkeypatch, status):
    """Test that rate limiting and server errors are retried."""
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_attempt(3),
    )
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "wait",
        wait_fixed(0),
    )
    mocked_responses.get(f"{DBT_CLOUD_ACCOUNT_URL}/projects/", status=status)
    mocked_responses.get(
        f"{DBT_CLOUD_ACCOUNT_URL}/projects/",
        json={"data": [], "status": {"is_success": True}},
    )

    response = call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="projects/")

    assert response["status"]["is_success"]
    assert len(mocked_responses.calls) == 2


def test_get_dbt_job_run_artifacts(mocked_responses, tmp_path):
    """Test that only JSON artifacts are downloaded to files."""
    mocked_responses.get(
        DBT_CLOUD_ARTIFACTS_URL,
        json={"data": ["compiled/model.sql", "manifest.json", "run_results.json"]},
    )
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json=MANIFEST)
    mocked_responses.get(
        f"{DBT_CLOUD_ARTIFACTS_URL}run_results.json", json={"results": []}
    )

    get_dbt_job_run_artifacts(account_id=ACCOUNT_ID, run_id=RUN_ID, output_dir=tmp_path)

    assert json.loads((tmp_path / "manifest.json").read_text()) == MANIFEST
    assert (tmp_path / "run_results.json").exists()
    assert not (tmp_path / "compiled").exists()


def test_get_dbt_job_run_artifacts_already_exists(mocked_responses, tmp_path):
    """Test that an existing artifact is not overwritten."""
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    Path(tmp_path / "manifest.json").touch()

    with pytest.raises(FileExistsError):
        get_dbt_job_run_artifacts(
            account_id=ACCOUNT_ID, run_id=RUN_ID, output_dir=tmp_path
        )


def test_get_dbt_job_run_artifacts_with_step(mocked_responses, tmp_path):
    """Test that the step is passed as a query parameter."""
    mocked_responses.get(
        DBT_CLOUD_ARTIFACTS_URL,
        json={"data": ["manifest.json"]},
        match=[matchers.query_param_matcher({"step": "4"})],
    )
    mocked_responses.get(
        f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json",
        json=MANIFEST,
        match=[matchers.query_param_matcher({"step": "4"})],
    )

    get_dbt_job_run_artifacts(
        account_id=ACCOUNT_ID, run_id=RUN_ID, output_dir=tmp_path, step=4
    )

    assert (tmp_path / "manifest.json").exists()


def test_get_dbt_job_run_artifacts_none_available(mocked_responses, tmp_path):
    """Test that a run without artifacts raises a clear error."""
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": None})

    with pytest.raises(RuntimeError, match="has no artifacts"):
        get_dbt_job_run_artifacts(
            account_id=ACCOUNT_ID, run_id=RUN_ID, output_dir=tmp_path
        )


def test_wait_for_dbt_cloud_job_run_status_queued_run(mocked_responses):
    """Test that a queued run (`in_progress: false`) is waited for until complete."""
    mocked_responses.get(DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=False))
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=False, in_progress=True)
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )

    assert wait_for_dbt_cloud_job_run_status(
        account_id=ACCOUNT_ID, run_id=RUN_ID, poll_interval_seconds=0
    )
    assert len(mocked_responses.calls) == 3


def test_wait_for_dbt_cloud_job_run_status_artifacts_not_yet_saved(mocked_responses):
    """Test that a complete run is waited for until its artifacts are saved."""
    mocked_responses.get(
        DBT_CLOUD_RUN_URL,
        json=dbt_cloud_run(is_complete=True, is_success=True, artifacts_saved=False),
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )

    assert wait_for_dbt_cloud_job_run_status(
        account_id=ACCOUNT_ID, run_id=RUN_ID, poll_interval_seconds=0
    )
    assert len(mocked_responses.calls) == 2


def test_wait_for_dbt_cloud_job_run_status_artifacts_never_saved(
    caplog, mocked_responses
):
    """Test that a complete run whose artifacts are never saved does not hang."""
    mocked_responses.get(
        DBT_CLOUD_RUN_URL,
        json=dbt_cloud_run(is_complete=True, is_success=True, artifacts_saved=False),
    )

    with caplog.at_level(logging.WARNING):
        assert wait_for_dbt_cloud_job_run_status(
            account_id=ACCOUNT_ID,
            run_id=RUN_ID,
            poll_interval_seconds=0,
            artifacts_saved_checks=3,
        )

    assert len(mocked_responses.calls) == 3
    assert "artifacts were not saved" in caplog.text


def test_wait_for_dbt_cloud_job_run_status_failed_run(mocked_responses):
    """Test that a failed run is reported as unsuccessful."""
    mocked_responses.get(DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True))

    assert not wait_for_dbt_cloud_job_run_status(
        account_id=ACCOUNT_ID, run_id=RUN_ID, poll_interval_seconds=0
    )


def test_dbt_cloud_auth_missing_token(monkeypatch):
    """Test that missing DBT_CLOUD_API_TOKEN raises ValueError."""
    monkeypatch.delenv("DBT_CLOUD_API_TOKEN", raising=False)
    with pytest.raises(
        ValueError, match="Environment variable 'DBT_CLOUD_API_TOKEN' is not set."
    ):
        call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="projects/")


def test_get_dbt_job_run_artifacts_overwrite(mocked_responses, tmp_path):
    """Test that an existing artifact is overwritten when overwrite=True."""
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json=MANIFEST)
    file_path = tmp_path / "manifest.json"
    file_path.write_text("old_content")

    downloaded = get_dbt_job_run_artifacts(
        account_id=ACCOUNT_ID, run_id=RUN_ID, output_dir=tmp_path, overwrite=True
    )
    assert downloaded == [str(file_path)]
    assert json.loads(file_path.read_text()) == MANIFEST


def test_get_dbt_job_run_artifacts_filtered(mocked_responses, tmp_path):
    """Test that only specifically requested artifacts are downloaded."""
    mocked_responses.get(
        DBT_CLOUD_ARTIFACTS_URL,
        json={"data": ["manifest.json", "run_results.json", "catalog.json"]},
    )
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json=MANIFEST)

    downloaded = get_dbt_job_run_artifacts(
        account_id=ACCOUNT_ID,
        run_id=RUN_ID,
        output_dir=tmp_path,
        artifacts=["manifest.json"],
    )
    assert downloaded == [str(tmp_path / "manifest.json")]
    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "run_results.json").exists()


def test_wait_for_dbt_cloud_job_run_status_timeout():
    """Test that wait_for_dbt_cloud_job_run_status times out when max_wait_seconds is exceeded."""
    with pytest.raises(TimeoutError, match="did not complete within 0s"):
        wait_for_dbt_cloud_job_run_status(
            account_id=ACCOUNT_ID,
            run_id=RUN_ID,
            poll_interval_seconds=0,
            max_wait_seconds=0,
        )
