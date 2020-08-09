.PHONY: all
all: format lint

.PHONY: format
format:
	@autoflake --remove-all-unused-imports --remove-unused-variables --ignore-init-module-imports --recursive --in-place .
	@isort -rc .
	@black .

.PHONY: lint
lint:
	@flake8 --exclude .git,__pycache__,docs/source/conf.py,old,build,dist \ .
	@black --check .
