
<div align="center">
  <a>
	<img src="https://img.shields.io/github/release/pgoslatara/dbt-cloud-download-artifacts-action.svg?logo=github">
  </a>
  <a>
	<img src="https://github.com/pgoslatara/dbt-cloud-download-artifacts-action/actions/workflows/ci_pipeline.yml/badge.svg">
  </a>
  <a>
	<img src="https://img.shields.io/badge/License-MIT-yellow.svg">
  </a>
  <a>
	<img src="https://img.shields.io/github/last-commit/pgoslatara/dbt-cloud-download-artifacts-action/main">
  </a>
  <a>
	<img src="https://img.shields.io/github/commits-since/pgoslatara/dbt-cloud-download-artifacts-action/latest">
  </a>
</div>

<div align="center">
  <a>
	<img src="https://img.shields.io/badge/style-ruff-41B5BE?style=flat">
  </a>
  <a>
	<img src="https://www.aschey.tech/tokei/github/pgoslatara/dbt-cloud-download-artifacts-action?category=code">
  </a>
</div>
<br/>

# dbt-cloud-download-artifacts-action

GitHub Action to download JSON artifacts from a dbt Cloud CI job triggered by a pull request.

# How to use

```yaml
name: CI pipeline

on:
  pull_request:
      branches:
          - main

jobs:
    download-dbt-artifacts:
        permissions:
          pull-requests: write
        runs-on: ubuntu-latest
        steps:
          - name: Download dbt artifacts
            uses: pgoslatara/dbt-cloud-download-artifacts-action@v1
            with:
              commit-sha: ${{ github.event.pull_request.head.sha }}
              dbt-cloud-api-token: ${{ secrets.DBT_CLOUD_API_TOKEN }}
              dbt-cloud-api-url-base: cloud.getdbt.com # Optional: Defaults to "cloud.getdbt.com".
              output-dir: target # Optional: Defaults to "target".
              step: 4 # Optional: Defaults to last step in CI job.
              verbose: true # Optional: Defaults to false.

          - name: Do something with the artifacts
            ...
```

# Contributing

Set up a local development environment, requires [uv](https://github.com/astral-sh/uv):
```bash
make install
```

Create API tokens for both dbt Cloud and GitHub. Copy `.env.example` to `.env` and update the values.

All tests can be run with
```bash
make test
```
