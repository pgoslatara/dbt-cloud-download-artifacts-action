import logging
from argparse import Namespace

from responses import matchers

from dbt_cloud_download_artifacts_action.main import arg_parser, cli

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


def test_main_passes_step(mocked_responses, monkeypatch, tmp_path) -> None:
    """Test that `--step` selects the artifacts of that step in the run."""
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha=COMMIT_SHA,
            output_dir=tmp_path,
            repo_name=REPO_NAME,
            step=4,
            verbose=False,
        ),
    )
    step_matcher = [matchers.query_param_matcher({"step": "4"})]
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )
    mocked_responses.get(
        DBT_CLOUD_ARTIFACTS_URL,
        json={"data": ["manifest.json"]},
        match=step_matcher,
    )
    mocked_responses.get(
        f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json",
        json={"nodes": {}},
        match=step_matcher,
    )

    cli()

    assert (tmp_path / "manifest.json").exists()


def test_arg_parser_defaults():
    """Test default values of arg_parser."""
    args = arg_parser(["--commit-sha", "abc1234", "--repo-name", "owner/repo"])
    assert args.commit_sha == "abc1234"
    assert args.repo_name == "owner/repo"
    assert args.output_dir == "./target"
    assert args.step is None
    assert args.verbose is False
    assert args.wait_timeout == 120
    assert args.job_timeout == 1800


def test_arg_parser_custom_options():
    """Test parsing custom arguments."""
    args = arg_parser(
        [
            "--commit-sha",
            "abc1234",
            "--repo-name",
            "owner/repo",
            "--output-dir",
            "./custom_target",
            "--step",
            "2",
            "--verbose",
            "--wait-timeout",
            "60",
            "--job-timeout",
            "600",
        ]
    )
    assert args.commit_sha == "abc1234"
    assert args.repo_name == "owner/repo"
    assert args.output_dir == "./custom_target"
    assert args.step == 2
    assert args.verbose is True
    assert args.wait_timeout == 60
    assert args.job_timeout == 600


def test_cli_accepts_passed_args(mocked_responses, tmp_path):
    """Test that cli() respects explicitly passed Namespace arguments."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )
    mocked_responses.get(
        DBT_CLOUD_RUN_URL, json=dbt_cloud_run(is_complete=True, is_success=True)
    )
    mocked_responses.get(DBT_CLOUD_ARTIFACTS_URL, json={"data": ["manifest.json"]})
    mocked_responses.get(f"{DBT_CLOUD_ARTIFACTS_URL}manifest.json", json={"nodes": {}})

    args = Namespace(
        commit_sha=COMMIT_SHA,
        job_timeout=1800,
        output_dir=str(tmp_path),
        repo_name=REPO_NAME,
        step=None,
        verbose=False,
        wait_timeout=120,
    )
    cli(args=args)

    assert (tmp_path / "manifest.json").exists()
