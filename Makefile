.PHONY: clean format install lint test

clean:
	rm -rf .coverage coverage.xml pytest-coverage.txt dist/ build/ .pytest_cache/ .ruff_cache/ .mypy_cache/ *.egg-info

format:
	uv run ruff format --config pyproject.toml .

install:
	uv sync --locked --extra dev

lint:
	uv run ruff check --config pyproject.toml .
	uv run mypy .

test:
	uv run pytest \
		--junitxml=coverage.xml \
		--cov-report=term-missing:skip-covered \
		--cov=src/dbt_cloud_download_artifacts_action/ \
		--numprocesses 3 \
		./tests
