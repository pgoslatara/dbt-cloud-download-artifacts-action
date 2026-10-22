
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

GitHub Action to download JSON artifacts (e.g. `manifest.json`, `run_results.json`) from a dbt Cloud CI job triggered by a pull request.

The action finds the dbt Cloud run through the "dbt Cloud" commit status that dbt Cloud posts on the pull request's head commit, waits for the run to complete and then downloads its JSON artifacts. If the run fails, the action logs a warning and still downloads any artifacts the run produced.

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
          contents: read
          statuses: read
        runs-on: ubuntu-latest
        steps:
          - name: Download dbt artifacts
            uses: pgoslatara/dbt-cloud-download-artifacts-action@v1
            with:
              commit-sha: ${{ github.event.pull_request.head.sha }}
              dbt-cloud-api-token: ${{ secrets.DBT_CLOUD_API_TOKEN }}
              dbt-cloud-api-url-base: cloud.getdbt.com # Optional: Defaults to "cloud.getdbt.com".
              output-dir: target # Optional: Defaults to ".".
              step: 4 # Optional: Defaults to last step in CI job.
              verbose: true # Optional: Defaults to false.

          - name: Do something with the artifacts
            ...
```

| Input | Required | Default | Description |
|---|---|---|---|
| `artifacts` | No | All JSON artifacts | Comma-separated list of artifact names to download (e.g. `manifest.json,run_results.json`). |
| `commit-sha` | Yes | | SHA of the commit that triggered the dbt Cloud CI job, usually `github.event.pull_request.head.sha`. |
| `dbt-cloud-api-token` | Yes | | dbt Cloud API token with read access to the CI job's runs. |
| `dbt-cloud-api-url-base` | No | Auto-detected / `cloud.getdbt.com` | Host of the dbt Cloud API, e.g. `ab123.us1.dbt.com`. Automatically detected from commit status URL if omitted. |
| `fail-on-run-failure` | No | `false` | Fail the action if the dbt Cloud CI job did not succeed. |
| `job-timeout` | No | `1800` | Maximum seconds to wait for the dbt Cloud job run to complete. |
| `output-dir` | No | `.` | Directory where the artifacts are saved. |
| `overwrite` | No | `false` | Overwrite existing artifact files if they already exist. |
| `repo-name` | No | `${{ github.repository }}` | Repository that holds the commit, in the form `<owner>/<repo>`. |
| `step` | No | Last step | Index of the step in the run to download artifacts from. The first step has index 1. |
| `verbose` | No | `false` | Log at debug level. |
| `wait-timeout` | No | `120` | Maximum seconds to wait for dbt Cloud CI commit status to appear. |

### Outputs

| Output | Description |
|---|---|
| `account-id` | dbt Cloud account ID. |
| `artifacts` | Comma-separated paths to downloaded artifacts. |
| `run-id` | dbt Cloud run ID. |
| `run-status` | Status of the dbt Cloud run (`success` or `failure`). |

The action reads the commit status with the job's `GITHUB_TOKEN` (or `PAT_GITHUB`), so the job needs the `statuses: read` permission.

The action does not check out your repository. If later steps need your repository's files, add `actions/checkout` before this action. A relative `output-dir` resolves against the job's working directory.

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

Every pull request runs pre-commit and the unit tests (`ci_pipeline.yml`) without access to any secrets. The integration test (`integration_pipeline.yml`) runs the pull request's version of the action against the dbt Cloud CI run for its head commit. For pull requests from forks, this job waits for a maintainer to approve it in the `fork-integration` environment, because it has access to the dbt Cloud API token. Check the diff before you approve.
