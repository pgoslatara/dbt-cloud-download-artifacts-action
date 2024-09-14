import semver

from dbt_cloud_download_artifacts_action.version import version


def test_version() -> None:
    """Check that version() returns a valid semantic version."""
    semver.Version.parse(version())
