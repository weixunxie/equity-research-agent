.PHONY: install install-dev api ui ui-install cli health test

TICKER ?= AAPL

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# `python -m` rather than the console script: a venv's scripts hard-code the
# path it was created at and break if the project folder is moved.
api:
	python -m uvicorn backend.main:app --reload --port 8000

test:
	python -m pytest -q

ui-install:
	cd frontend && npm install

ui:
	cd frontend && npm run dev

cli:
	python -m scripts.research_cli $(TICKER)

health:
	curl -s http://localhost:8000/health | python -m json.tool
