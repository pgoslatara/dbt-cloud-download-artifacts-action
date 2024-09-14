import argparse
import logging
from pathlib import Path

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    get_dbt_job_run_artifact,
    wait_for_dbt_cloud_job_status,
)
from dbt_cloud_download_artifacts_action.github_helpers import (
    get_latest_dbt_run_id_per_pull_request,
)
from dbt_cloud_download_artifacts_action.logger import configure_console_logging
from dbt_cloud_download_artifacts_action.version import version


def cli() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", type=str, required=True)
    parser.add_argument("--output-dir", default="./tmp", type=str, required=False)
    parser.add_argument("--repo-name", type=str, required=True)
    parser.add_argument("--step", default=None, type=int, required=False)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    configure_console_logging(verbose=args.verbose)
    logging.info(f"Running `dbt-cloud-download-artifacts-action` ({version()})...")
    logging.debug(f"{args=}")

    dbt_account_id, dbt_run_id = get_latest_dbt_run_id_per_pull_request(
        commit_sha=args.commit_sha, repo_name=args.repo_name
    )
    wait_for_dbt_cloud_job_status(account_id=dbt_account_id, run_id=dbt_run_id)
    get_dbt_job_run_artifact(
        account_id=dbt_account_id,
        artifact_name="manifest.json",
        output_dir=Path(args.output_dir),
        run_id=dbt_run_id,
    )
