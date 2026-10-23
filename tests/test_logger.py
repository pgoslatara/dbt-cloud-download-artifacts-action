from argparse import Namespace

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from tenacity import stop_after_delay

from dbt_cloud_download_artifacts_action.dbt_cloud_helpers import (
    call_dbt_cloud_api,
)
from dbt_cloud_download_artifacts_action.github_helpers import (
    call_github_api,
)
from dbt_cloud_download_artifacts_action.main import cli

from .pytest_helpers import catch_logs, records_to_tuples


def test_logging_debug(monkeypatch) -> None:
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.setattr(
        call_github_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha="123456",
            output_dir="./target",
            repo_name="test",
            step=None,
            verbose=True,
        ),
    )

    with catch_logs() as handler, pytest.raises(RequestsConnectionError):
        cli()

    assert (
        len(
            [
                record
                for record in records_to_tuples(handler.records)
                if record[2].startswith("args=Namespace")
            ]
        )
        == 1
    )


def test_logging_info(monkeypatch) -> None:
    monkeypatch.setattr(
        call_dbt_cloud_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.setattr(
        call_github_api.retry,  # type: ignore[attr-defined]
        "stop",
        stop_after_delay(0),
    )
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.main.arg_parser",
        lambda: Namespace(
            commit_sha="123456",
            output_dir="./target",
            repo_name="test",
            step=None,
            verbose=False,
        ),
    )

    with catch_logs() as handler, pytest.raises(RequestsConnectionError):
        cli()

    assert (
        len(
            [
                record
                for record in records_to_tuples(handler.records)
                if record[2].startswith("Running `dbt-cloud-download-artifacts-action`")
            ]
        )
        == 1
    )
