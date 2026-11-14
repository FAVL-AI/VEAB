.PHONY: install test serve suite lint
install:
	python -m pip install -e '.[test]'
test:
	python -m pytest -q
lint:
	python -m compileall -q veap
serve:
	python -m uvicorn veap.api:app --host 127.0.0.1 --port 8000
suite:
	python -m veap suite --seeds 0 1 2 --out artifacts/suite-summary.json
