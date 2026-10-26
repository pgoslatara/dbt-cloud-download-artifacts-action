import argparse
import logging
import os
from argparse import Namespace
from pathlib import Path
from typing import Any, Optional, Sequence

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    get_dbt_job_run_artifacts,
    wait_for_dbt_cloud_job_run_status,
)
from dbt_cloud_download_artifacts_action.github_helpers import (
    get_dbt_run_id_per_commit_sha,
)
from dbt_cloud_download_artifacts_action.logger import configure_console_logging
from dbt_cloud_download_artifacts_action.version import version

logger = logging.getLogger(__name__)


def write_github_output(name: str, value: Any) -> None:
    """Write an output key-value pair to the GITHUB_OUTPUT environment file."""
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file and Path(output_file).exists():
        with Path(output_file).open("a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def cli(args: Optional[Namespace] = None) -> None:
    """CLI entrypoint.

    Raises:
        RuntimeError: If the dbt Cloud run did not succeed and fail_on_run_failure is True.

    """
    args = args or arg_parser()
    configure_console_logging(verbose=args.verbose)
    logger.info(f"Running `dbt-cloud-download-artifacts-action` ({version()})...")
    logger.debug(f"{args=}")

    wait_timeout = getattr(args, "wait_timeout", 120)
    dbt_account_id, dbt_run_id, dbt_host = get_dbt_run_id_per_commit_sha(
        commit_sha=args.commit_sha,
        repo_name=args.repo_name,
        wait_timeout_seconds=wait_timeout,
    )

    api_url_base = (
        getattr(args, "dbt_cloud_api_url_base", None)
        or os.getenv("DBT_CLOUD_API_URL_BASE")
        or dbt_host
    )
    job_timeout = getattr(args, "job_timeout", 1800)
    run_succeeded = wait_for_dbt_cloud_job_run_status(
        account_id=dbt_account_id,
        api_url_base=api_url_base,
        max_wait_seconds=job_timeout,
        run_id=dbt_run_id,
    )

    if not run_succeeded:
        msg = (
            f"dbt Cloud run {dbt_run_id} did not succeed. Its artifacts exist only if "
            "dbt itself ran: a run that failed before dbt started has none. See the run in dbt Cloud for the error."
        )
        if getattr(args, "fail_on_run_failure", False):
            raise RuntimeError(msg)
        logger.warning(msg)

    artifacts_filter = None
    if getattr(args, "artifacts", None):
        artifacts_filter = [a.strip() for a in args.artifacts.split(",") if a.strip()]

    downloaded_files = get_dbt_job_run_artifacts(
        account_id=dbt_account_id,
        api_url_base=api_url_base,
        artifacts=artifacts_filter,
        output_dir=Path(args.output_dir),
        overwrite=getattr(args, "overwrite", False),
        run_id=dbt_run_id,
        step=args.step,
    )

    write_github_output("account-id", dbt_account_id)
    write_github_output("artifacts", ",".join(downloaded_files))
    write_github_output("run-id", dbt_run_id)
    write_github_output("run-status", "success" if run_succeeded else "failure")


def arg_parser(argv: Optional[Sequence[str]] = None) -> Namespace:
    """Parse command line arguments.

    Args:
        argv (Sequence[str], optional): Arguments to parse. Defaults to sys.argv[1:].

    Returns:
        Namespace: Parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description="Download dbt artifacts from dbt Cloud."
    )
    parser.add_argument(
        "--artifacts",
        default=None,
        help="Comma-separated list of artifact names to download (e.g. 'manifest.json,run_results.json').",
        required=False,
        type=str,
    )
    parser.add_argument("--commit-sha", required=True, type=str)
    parser.add_argument(
        "--dbt-cloud-api-url-base",
        default=None,
        help="Base URL of the dbt Cloud API.",
        required=False,
        type=str,
    )
    parser.add_argument(
        "--fail-on-run-failure",
        action="store_true",
        help="Fail if the dbt Cloud run did not succeed.",
    )
    parser.add_argument(
        "--job-timeout",
        default=1800,
        help="Maximum seconds to wait for the dbt Cloud job run to complete.",
        required=False,
        type=int,
    )
    parser.add_argument("--output-dir", default=".", required=False, type=str)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing artifact files if they already exist.",
    )
    parser.add_argument("--repo-name", required=True, type=str)
    parser.add_argument("--step", default=None, required=False, type=int)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=version())
    parser.add_argument(
        "--wait-timeout",
        default=120,
        help="Maximum seconds to wait for dbt Cloud CI commit status.",
        required=False,
        type=int,
    )

    return parser.parse_args(argv)
