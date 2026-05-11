.PHONY: help run test ci ingest docker-build

help:
	@echo "Targets: run | test | ci | ingest | docker-build (needs Docker)"

run:
	uvicorn app.main:app --reload --port 8088

test:
	pytest tests/ -q --tb=short

ci:
	bash scripts/ci_local.sh

ingest:
	python scripts/ingest_manuals.py

docker-build:
	docker build -t audi-vcds-master .
