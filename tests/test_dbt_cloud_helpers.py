import os
from pathlib import Path

import pytest
from tenacity import RetryError, stop_after_delay

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    call_dbt_cloud_api,
    get_dbt_job_run_artifacts,
)


def test_dbt_cloud_api_connection(monkeypatch):
    """Test that the dbt Cloud API can be reached"""
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    response = call_dbt_cloud_api(
        account_id=os.getenv("DBT_ACCOUNT_ID"), endpoint="projects/"
    )
    assert response["status"]["is_success"]


def test_dbt_cloud_api_connection_errors(monkeypatch):
    """Test that a RuntimeError is raised for invalid endpoint."""
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    with pytest.raises(RetryError):
        call_dbt_cloud_api(
            account_id=os.getenv("DBT_ACCOUNT_ID"), endpoint="non_existent_endpoint/"
        )


def test_get_dbt_job_run_artifacts(monkeypatch, tmp_path):
    """Test that a manifest can be downloaded to a file."""
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    run_id = os.getenv("DBT_RUN_ID")

    file_name = tmp_path / "manifest.json"
    assert not file_name.exists()
    get_dbt_job_run_artifacts(
        account_id=os.getenv("DBT_ACCOUNT_ID"),
        run_id=run_id,
        output_dir=tmp_path,
    )
    assert file_name.exists()


def test_get_dbt_job_run_artifacts_already_exists(monkeypatch, tmp_path):
    """Test that a manifest can be downloaded to a file."""
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    run_id = os.getenv("DBT_RUN_ID")

    file_name = tmp_path / "manifest.json"
    Path(file_name).touch()
    assert file_name.exists()
    with pytest.raises(FileExistsError):
        get_dbt_job_run_artifacts(
            account_id=os.getenv("DBT_ACCOUNT_ID"),
            run_id=run_id,
            output_dir=tmp_path,
        )


def test_get_dbt_job_run_artifacts_with_step(monkeypatch, tmp_path):
    """Test that a manifest can be downloaded to a file."""
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    run_id = os.getenv("DBT_RUN_ID")

    file_name = tmp_path / "manifest.json"
    assert not file_name.exists()
    get_dbt_job_run_artifacts(
        account_id=os.getenv("DBT_ACCOUNT_ID"),
        run_id=run_id,
        output_dir=tmp_path,
        step=4,
    )
    assert file_name.exists()
