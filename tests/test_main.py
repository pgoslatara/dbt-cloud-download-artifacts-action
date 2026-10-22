import logging
from argparse import Namespace

from dbt_cloud_download_artifacts_action.main import cli

from .conftest import (
    COMMIT_SHA,
    DBT_CLOUD_ARTIFACTS_URL,
    DBT_CLOUD_RUN_URL,
    GITHUB_COMMIT_STATUS_URL,
    REPO_NAME,
    dbt_cloud_commit_status,
    dbt_cloud_run,
)


def test_main_happy_path(mocked_responses, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.dbt_cloud_helpers.time.sleep",
        lambda _: None,
    )
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha=COMMIT_SHA,
            output_dir=tmp_path,
            repo_name=REPO_NAME,
            step=None,
            verbose=False,
        ),
    )
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=False))
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json={"nodes": {}})

    cli()

    assert (tmp_path / "manifest.json").exists()


def test_main_failed_run_warns_and_downloads(
    caplog, mocked_responses, monkeypatch, tmp_path
) -> None:
    """Test that a failed run logs a warning and still downloads its artifacts.

    A run that fails inside `dbt build` still writes `manifest.json`.
    """
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha=COMMIT_SHA,
            output_dir=tmp_path,
            repo_name=REPO_NAME,
            step=None,
            verbose=False,
        ),
    )
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=False)
    )
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json={"nodes": {}})

    with caplog.at_level(logging.WARNING):
        cli()

    assert (tmp_path / "manifest.json").exists()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "did not succeed" in warnings[0].getMessage()
