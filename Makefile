.PHONY: run test load clean help

run: ## Pull image, start service, run all tests + load test, write reports
	docker compose up --build --abort-on-container-exit --exit-code-from tests

test: ## Run functional tests only (service must be running on localhost:8080)
	pytest tests/ -v \
		--html=reports/report.html \
		--self-contained-html \
		--tb=short \
		-p no:warnings

load: ## Run load test only (service must be running on localhost:8080)
	locust -f load_tests/locustfile.py \
		--headless \
		--host=http://localhost:8080 \
		--users=1000 \
		--spawn-rate=10 \
		--run-time=60s \
		--html=reports/load_report.html \
		--only-summary

clean: ## Stop containers and remove reports
	docker compose down -v --remove-orphans
	rm -rf reports/*

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'
