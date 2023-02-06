.PHONY: all
all: format lint

.PHONY: format
format:
	@autoflake --remove-all-unused-imports --remove-unused-variables --ignore-init-module-imports --recursive --in-place .
	@isort .
	@black .

.PHONY: lint
lint:
	@flake8 ./noaa_coops ./tests

# @black --check .

.PHONY: type-check
type-check:
	@mypy .
