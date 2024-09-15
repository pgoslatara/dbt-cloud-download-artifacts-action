import argparse
import logging
from argparse import Namespace
from pathlib import Path
from typing import Optional

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    get_dbt_job_run_artifacts,
    wait_for_dbt_cloud_job_run_status,
)
from dbt_cloud_download_artifacts_action.github_helpers import (
    get_dbt_run_id_per_commit_sha,
)
from dbt_cloud_download_artifacts_action.logger import configure_console_logging
from dbt_cloud_download_artifacts_action.version import version


def cli(args: Optional[Namespace] = None) -> None:
    """CLI entrypoint."""
    args = arg_parser()
    configure_console_logging(verbose=args.verbose)
    logging.info(f"Running `dbt-cloud-download-artifacts-action` ({version()})...")
    logging.debug(f"{args=}")

    dbt_account_id, dbt_run_id = get_dbt_run_id_per_commit_sha(
        commit_sha=args.commit_sha, repo_name=args.repo_name
    )
    wait_for_dbt_cloud_job_run_status(account_id=dbt_account_id, run_id=dbt_run_id)
    get_dbt_job_run_artifacts(
        account_id=dbt_account_id,
        output_dir=Path(args.output_dir),
        run_id=dbt_run_id,
    )


def arg_parser() -> Namespace:
    """Parse command line arguments.

    Returns:
        Namespace: Parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description="Download dbt artifacts from dbt Cloud."
    )
    parser.add_argument("--commit-sha", type=str, required=True)
    parser.add_argument("--output-dir", default="./tmp", type=str, required=False)
    parser.add_argument("--repo-name", type=str, required=True)
    parser.add_argument("--step", default=None, type=int, required=False)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=version())

    return parser.parse_args()
