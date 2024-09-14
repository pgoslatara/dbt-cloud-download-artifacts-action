import os
from argparse import Namespace

from tenacity import stop_after_delay

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    call_dbt_cloud_api,
)
from dbt_cloud_download_artifacts_action.github_helpers import (
    call_github_api,
)
from dbt_cloud_download_artifacts_action.main import cli


def test_main_happy_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(call_dbt_cloud_api.retry, "stop", stop_after_delay(0))
    monkeypatch.setattr(call_github_api.retry, "stop", stop_after_delay(0))
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha=os.getenv("COMMIT_SHA"),
            output_dir=tmp_path,
            repo_name=os.getenv("REPO_NAME"),
            step=None,
            verbose=False,
        ),
    )

    cli()
