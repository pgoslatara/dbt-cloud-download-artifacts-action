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
    assert r == (ACCOUNT_ID, RUN_ID, "cloud.getdbt.com")


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

    assert r == (ACCOUNT_ID, RUN_ID, "cloud.getdbt.com")
    assert len(mocked_responses.calls) == 2


def test_get_dbt_run_id_per_commit_sha_timeout(mocked_responses):
    """Test that the lookup times out if no dbt Cloud commit status appears."""
    mocked_responses.get(GITHUB_COMMIT_STATUS_URL, json={"statuses": []})
    with pytest.raises(TimeoutError, match="No dbt Cloud CI job found"):
        get_dbt_run_id_per_commit_sha(
            commit_sha=COMMIT_SHA, repo_name=REPO_NAME, wait_timeout_seconds=0
        )


def test_get_dbt_run_id_per_commit_sha_empty_args():
    """Test that empty commit_sha or repo_name raises ValueError."""
    with pytest.raises(ValueError, match="commit_sha must not be empty"):
        get_dbt_run_id_per_commit_sha(commit_sha="", repo_name=REPO_NAME)
    with pytest.raises(ValueError, match="repo_name must not be empty"):
        get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name="")


def test_github_api_connection(mocked_responses):
    """Test that the GitHub API is called with the token."""
    mocked_responses.get(
        "https://api.github.com/user",
        json={"id": 1},
        match=[matchers.header_matcher({"Authorization": "Bearer dummy-github-token"})],
    )
    response = call_github_api(endpoint="user")
    assert isinstance(response["id"], int)


def test_github_auth_fallback(mocked_responses, monkeypatch):
    """Test that GITHUB_TOKEN is used if PAT_GITHUB is unset."""
    monkeypatch.delenv("PAT_GITHUB", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "token-from-github-token")
    mocked_responses.get(
        "https://api.github.com/user",
        json={"id": 1},
        match=[
            matchers.header_matcher({"Authorization": "Bearer token-from-github-token"})
        ],
    )
    response = call_github_api(endpoint="user")
    assert response["id"] == 1


def test_github_auth_missing_token(monkeypatch):
    """Test that missing both tokens raises ValueError."""
    monkeypatch.delenv("PAT_GITHUB", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(
        ValueError,
        match=r"Neither 'PAT_GITHUB' nor 'GITHUB_TOKEN' environment variable is set\.",
    ):
        call_github_api(endpoint="user")


def test_github_api_connection_nonexisting_endpoint(mocked_responses):
    """Test that an invalid endpoint raises a non-retryable error."""
    mocked_responses.get("https://api.github.com/I_don_t_exist", status=404)
    with pytest.raises(NonRetryableHTTPError, match="404"):
        call_github_api(endpoint="I_don_t_exist")


@pytest.mark.parametrize(
    ("target_url", "expected_host"),
    [
        (
            f"https://cloud.getdbt.com/deploy/{ACCOUNT_ID}/projects/380303/runs/{RUN_ID}",
            "cloud.getdbt.com",
        ),
        (
            f"https://ab123.us1.dbt.com/deploy/{ACCOUNT_ID}/projects/380303/runs/{RUN_ID}/?tab=artifacts",
            "ab123.us1.dbt.com",
        ),
    ],
)
def test_get_dbt_run_id_per_commit_sha_url_formats(
    mocked_responses, target_url, expected_host
):
    """Test that the run id is parsed without a trailing slash or with a query string."""
    mocked_responses.get(
        GITHUB_COMMIT_STATUS_URL,
        json={"statuses": [{**dbt_cloud_commit_status(), "target_url": target_url}]},
    )
    r = get_dbt_run_id_per_commit_sha(commit_sha=COMMIT_SHA, repo_name=REPO_NAME)
    assert r == (ACCOUNT_ID, RUN_ID, expected_host)


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
