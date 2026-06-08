.PHONY: install api ui ui-install cli health

TICKER ?= AAPL

install:
	pip install -r requirements.txt

api:
	uvicorn backend.main:app --reload --port 8000

ui-install:
	cd frontend && npm install

ui:
	cd frontend && npm run dev

cli:
	python -m scripts.research_cli $(TICKER)

health:
	curl -s http://localhost:8000/health | python -m json.tool
