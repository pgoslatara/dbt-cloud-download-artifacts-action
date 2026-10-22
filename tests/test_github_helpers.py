import pytest
from responses import matchers

from dbt_cloud_download_artifacts_action.github_helpers import (
    call_github_api,
    get_dbt_run_id_per_commit_sha,
)
from dbt_cloud_download_artifacts_action.utils import NonRetryableHTTPError

from .conftest import (
    ACCOUNT_ID,
    COMMIT_SHA,
    GITHUB_COMMIT_STATUS_URL,
    REPO_NAME,
    RUN_ID,
    dbt_cloud_commit_status,
)


def test_get_dbt_run_id_per_commit_sha(mocked_responses):
    """Test that the dbt Cloud run id can be retrieved for a commit sha."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL,
        json={"statuses": [{"context": "pre-commit"}, dbt_cloud_commit_status()]},
    )
    r = get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name=REPO_NAME)
    assert r == (ACCOUNT_ID, RUN_ID)


def test_get_dbt_run_id_per_commit_sha_waits_for_status(mocked_responses, monkeypatch):
    """Test that the lookup retries until dbt Cloud has posted its commit status."""
    monkeypatch.setattr(
        "dbt_cloud_download_artifacts_action.github_helpers.time.sleep", lambda _: None
    )
    mocked_responses.get(GITHUB_COMMIT_STATUS_URL, json={"statuses": []})
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL, json={"statuses": [dbt_cloud_commit_status()]}
    )

    r = get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name=REPO_NAME)

    assert r == (ACCOUNT_ID, RUN_ID)
    assert len(mocked_responses.calls) == 2


def test_github_api_connection(mocked_responses):
    """Test that the GitHub API is called with the token."""
    mocked_responses.get(
        "https://api.github.com/user",
        json={"id": 1},
        match=[matchers.header_matcher({"Authorization": "Bearer dummy-github-token"})],
    )
    response = call_github_api(endpoint="user")
    assert isinstance(response["id"], int)


def test_github_api_connection_nonexisting_endpoint(mocked_responses):
    """Test that an invalid endpoint raises a non-retryable error."""
    mocked_responses.get("https://api.github.com/I_don_t_exist", status=404)
    with pytest.raises(NonRetryableHTTPError, match="404"):
        call_github_api(endpoint="I_don_t_exist")


@pytest.mark.parametrize(
    "target_url",
    [
        f"https://cloud.getdbt.com/deploy/{ACCOUNT_ID}/projects/380303/runs/{RUN_ID}",
        f"https://ab123.us1.dbt.com/deploy/{ACCOUNT_ID}/projects/380303/runs/{RUN_ID}/?tab=artifacts",
    ],
)
def test_get_dbt_run_id_per_commit_sha_url_formats(mocked_responses, target_url):
    """Test that the run id is parsed without a trailing slash or with a query string."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL,
        json={"statuses": [{**dbt_cloud_commit_status(), "target_url": target_url}]},
    )
    r = get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name=REPO_NAME)
    assert r == (ACCOUNT_ID, RUN_ID)


def test_get_dbt_run_id_per_commit_sha_unparseable_url(mocked_responses):
    """Test that a status without a dbt Cloud run URL raises a clear error."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL,
        json={
            "statuses": [
                {**dbt_cloud_commit_status(), "target_url": "https://example.com/"}
            ]
        },
    )
    with pytest.raises(RuntimeError, match="Could not parse"):
        get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name=REPO_NAME)
