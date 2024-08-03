.PHONY: all
all: format lint

.PHONY: format
format:
	@ruff format .

.PHONY: lint
lint:
	@ruff check ./noaa_coops/ ./tests/

# @black --check .

.PHONY: type-check
type-check:
	@mypy .
