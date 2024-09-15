from importlib.metadata import version as importlib_version


def version() -> str:
    """Get the version of `dbt-cloud-download-artifacts-action`.

    Returns:
        str: The version of `dbt-cloud-download-artifacts-action`.

    """
    return importlib_version("dbt-cloud-download-artifacts-action")
