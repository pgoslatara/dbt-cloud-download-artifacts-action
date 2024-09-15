
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

A GitHub Action to download JSON artifacts from a dbt Cloud CI job triggered by a pull request.

# How to use

```yaml
name: CI pipeline

on:
  pull_request:
      branches:
          - main

jobs:
    download-artifacts:
        runs-on: ubuntu-latest
        permissions:
            id-token: write
        steps:
          - name: Download dbt artifacts
            uses: pgoslatara/dbt-cloud-download-artifacts-action@v0
            with:
              commit-sha: ${{ github.sha }}
              dbt_cloud_api_token: ${{ secrets.DBT_CLOUD_API_TOKEN }}
              output-dir: target # Optional: Defaults to ".".
              step: 4 # Optional: Defaults to last step in CI job.
              verbose: true # Optional: Defaults to false.

          - name: Do something with the artifacts
            ...
```
