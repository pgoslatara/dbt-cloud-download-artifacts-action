# dbt-cloud-download-artifacts-action

A GitHub Action to download artifacts from a dbt Cloud CI job triggered by a pull request.

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
            id-token: read
        steps:
          - name: Download dbt artifacts
            uses: pgoslatara/dbt-cloud-download-artifacts-action@X
            with:
              commit-sha: ${{ github.sha }}
              dbt_cloud_api_token: ${{ secrets.DBT_CLOUD_API_TOKEN }}
              output-dir: target # Optional: Defaults to ".".
              step: 4 # Optional: Defaults to last step in CI job.
              verbose: true # Optional: Defaults to false.

          - name: Do something with the artifacts
            ...
```
