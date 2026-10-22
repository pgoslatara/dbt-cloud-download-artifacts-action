import argparse
import logging
from argparse import Namespace
from collections.abc import Sequence
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
    if args is None:
        args = arg_parser()
    configure_console_logging(verbose=args.verbose)
    logging.info(f"Running `dbt-cloud-download-artifacts-action` ({version()})...")
    logging.debug(f"{args=}")

    dbt_account_id, dbt_run_id, _ = get_dbt_run_id_per_commit_sha(
        commit_sha=args.commit_sha,
        repo_name=args.repo_name,
        wait_timeout_seconds=getattr(args, "wait_timeout", 120),
    )
    run_succeeded = wait_for_dbt_cloud_job_run_status(
        account_id=dbt_account_id,
        max_wait_seconds=getattr(args, "job_timeout", 1800),
        run_id=dbt_run_id,
    )
    # We warn here rather than stopping, since a failed run still has artifacts.
    if not run_succeeded:
        logging.warning(
            f"dbt Cloud run {dbt_run_id} did not succeed. Its artifacts exist only if "
            "dbt itself ran: a run that failed before dbt started has none. See the run in dbt Cloud for the error."
        )
    get_dbt_job_run_artifacts(
        account_id=dbt_account_id,
        output_dir=Path(args.output_dir),
        run_id=dbt_run_id,
        step=args.step,
    )


def arg_parser(argv: Optional[Sequence[str]] = None) -> Namespace:
    """Parse command line arguments.

    Args:
        argv (Optional[Sequence[str]], optional): Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Namespace: Parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description="Download dbt artifacts from dbt Cloud."
    )
    parser.add_argument("--commit-sha", type=str, required=True)
    parser.add_argument(
        "--job-timeout",
        default=1800,
        help="Maximum time in seconds to wait for the dbt Cloud job run to complete. Defaults to 1800.",
        type=int,
    )
    parser.add_argument("--output-dir", default="./target", type=str, required=False)
    parser.add_argument("--repo-name", type=str, required=True)
    parser.add_argument("--step", default=None, type=int, required=False)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=version())
    parser.add_argument(
        "--wait-timeout",
        default=120,
        help="Maximum time in seconds to wait for dbt Cloud status to appear on commit. Defaults to 120.",
        type=int,
    )

    return parser.parse_args(argv)
