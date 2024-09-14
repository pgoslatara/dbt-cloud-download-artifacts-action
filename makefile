install:
	uv pip install -e .[dev]

test:
	uv run pytest \
		-c ./tests \
		--junitxml=coverage.xml \
		--cov-report=term-missing:skip-covered \
		--cov=src/dbt_cloud_download_artifacts_action/ \
		--numprocesses 3 \
		./tests
