.PHONY: install test serve suite lint
install:
	python -m pip install -e '.[test]'
test:
	python -m pytest -q
lint:
	python -m compileall -q veab
serve:
	python -m uvicorn veab.api:app --host 127.0.0.1 --port 8000
suite:
	python -m veab suite --seeds 0 1 2 --out artifacts/suite-summary.json
