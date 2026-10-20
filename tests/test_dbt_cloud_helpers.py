import json
from pathlib import Path

import pytest
from responses import matchers
from tenacity import RetryError

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    call_dbt_cloud_api,
    get_dbt_job_run_artifacts,
    wait_for_dbt_cloud_job_run_status,
)

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


def test_dbt_cloud_api_connection_errors(mocked_responses):
    """Test that a RetryError is raised for an invalid endpoint."""
    mocked_responses.get(f"{DBT_CLOUD_ACCOUNT_URL}/non_existent_endpoint/", status=404)
    with pytest.raises(RetryError):
        call_dbt_cloud_api(account_id=ACCOUNT_ID, endpoint="non_existent_endpoint/")


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
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
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


def test_wait_for_dbt_cloud_job_run_status_failed_run(mocked_responses):
    """Test that a failed run is reported as unsuccessful."""
    mocked_responses.get(DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True))

    assert not wait_for_dbt_cloud_job_run_status(
        account_id=ACCOUNT_ID, run_id=RUN_ID, poll_interval_seconds=0
    )
