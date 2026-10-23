import logging
from argparse import Namespace

import pytest
from responses import matchers

from dbt_cloud_download_artifacts_action.main import (
    arg_parser,
    cli,
    write_github_output,
)

from .conftest import (
    ACCOUNT_ID,
    COMMIT_SHA,
    DBT_CLOUD_ARTIFACTS_URL,
    DBT_CLOUD_RUN_URL,
    GITHUB_COMMIT_STATUS_URL,
    REPO_NAME,
    RUN_ID,
    dbt_cloud_commit_status,
    dbt_cloud_run,
)


def test_arg_parser_defaults() -> None:
    """Test argument parser with default values."""
    args = arg_parser(["--commit-sha", "123456", "--repo-name", "org/repo"])
    assert args.commit_sha == "123456"
    assert args.repo_name == "org/repo"
    assert args.output_dir == "."
    assert args.step is None
    assert args.verbose is False
    assert args.artifacts is None
    assert args.dbt_cloud_api_url_base is None
    assert args.fail_on_run_failure is False
    assert args.overwrite is False
    assert args.job_timeout == 1800
    assert args.wait_timeout == 120


def test_arg_parser_custom_options() -> None:
    """Test argument parser with custom values."""
    args = arg_parser(
        [
            "--artifacts",
            "manifest.json,run_results.json",
            "--commit-sha",
            "123456",
            "--dbt-cloud-api-url-base",
            "custom.dbt.com",
            "--fail-on-run-failure",
            "--job-timeout",
            "600",
            "--output-dir",
            "custom_dir",
            "--overwrite",
            "--repo-name",
            "org/repo",
            "--step",
            "2",
            "--verbose",
            "--wait-timeout",
            "60",
        ]
    )
    assert args.artifacts == "manifest.json,run_results.json"
    assert args.dbt_cloud_api_url_base == "custom.dbt.com"
    assert args.fail_on_run_failure is True
    assert args.job_timeout == 600
    assert args.output_dir == "custom_dir"
    assert args.overwrite is True
    assert args.repo_name == "org/repo"
    assert args.step == 2
    assert args.verbose is True
    assert args.wait_timeout == 60


def test_main_happy_path(mocked_responses, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.dbt_cloud_helpers.time.sleep",
        lambda _: None,
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

    args = Namespace(
        artifacts=None,
        commit_sha=COMMIT_SHA,
        dbt_cloud_api_url_base=None,
        fail_on_run_failure=False,
        job_timeout=1800,
        output_dir=str(tmp_path),
        overwrite=False,
        repo_name=REPO_NAME,
        step=None,
        verbose=False,
        wait_timeout=120,
    )
    cli(args=args)

    assert (tmp_path / "manifest.json").exists()


def test_main_failed_run_warns_and_downloads(
    caplog, mocked_responses, tmp_path
) -> None:
    """Test that a failed run logs a warning and still downloads its artifacts."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=False)
    )
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json={"nodes": {}})

    args = Namespace(
        artifacts=None,
        commit_sha=COMMIT_SHA,
        dbt_cloud_api_url_base=None,
        fail_on_run_failure=False,
        job_timeout=1800,
        output_dir=str(tmp_path),
        overwrite=False,
        repo_name=REPO_NAME,
        step=None,
        verbose=False,
        wait_timeout=120,
    )
    with caplog.at_level(logging.WARNING):
        cli(args=args)

    assert (tmp_path / "manifest.json").exists()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "did not succeed" in warnings[0].getMessage()


def test_main_failed_run_raises_when_fail_on_run_failure(
    mocked_responses, tmp_path
) -> None:
    """Test that a failed run raises RuntimeError when fail_on_run_failure=True."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=False)
    )

    args = Namespace(
        artifacts=None,
        commit_sha=COMMIT_SHA,
        dbt_cloud_api_url_base=None,
        fail_on_run_failure=True,
        job_timeout=1800,
        output_dir=str(tmp_path),
        overwrite=False,
        repo_name=REPO_NAME,
        step=None,
        verbose=False,
        wait_timeout=120,
    )
    with pytest.raises(RuntimeError, match="did not succeed"):
        cli(args=args)


def test_main_passes_step_and_filters_artifacts(mocked_responses, tmp_path) -> None:
    """Test that `--step` and `--artifacts` filter artifacts properly."""
    step_matcher = [matchers.query_param_matcher({"step": "4"})]
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )
    mocked_responses.get(
        DBT_CLOUD_ARTIFACTS_URL,
        json={"data": ["manifest.json", "run_results.json"]},
        match=step_matcher,
    )
    mocked_responses.get(
        f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json",
        json={"nodes": {}},
        match=step_matcher,
    )

    args = Namespace(
        artifacts="manifest.json",
        commit_sha=COMMIT_SHA,
        dbt_cloud_api_url_base=None,
        fail_on_run_failure=False,
        job_timeout=1800,
        output_dir=str(tmp_path),
        overwrite=False,
        repo_name=REPO_NAME,
        step=4,
        verbose=False,
        wait_timeout=120,
    )
    cli(args=args)

    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "run_results.json").exists()


def test_main_writes_github_output(mocked_responses, monkeypatch, tmp_path) -> None:
    """Test that CLI writes outputs to GITHUB_OUTPUT."""
    output_file = tmp_path / "github_output.txt"
    output_file.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json={"nodes": {}})

    args = Namespace(
        artifacts=None,
        commit_sha=COMMIT_SHA,
        dbt_cloud_api_url_base=None,
        fail_on_run_failure=False,
        job_timeout=1800,
        output_dir=str(tmp_path),
        overwrite=False,
        repo_name=REPO_NAME,
        step=None,
        verbose=False,
        wait_timeout=120,
    )
    cli(args=args)

    output_content = output_file.read_text(encoding="utf-8")
    assert f"account-id={ACCOUNT_ID}" in output_content
    assert f"run-id={RUN_ID}" in output_content
    assert "run-status=success" in output_content
    assert f"artifacts={tmp_path / 'manifest.json'}" in output_content


def test_write_github_output_noop_when_unset(monkeypatch) -> None:
    """Test that write_github_output does nothing when GITHUB_OUTPUT is not set."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    write_github_output("key", "value")
