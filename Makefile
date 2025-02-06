.PHONY: build run stop help

# Default target when just running 'make'
.DEFAULT_GOAL := help

# Colors for help message
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)

help: ## Show this help
	@echo 'Usage:'
	@echo '  ${YELLOW}make${RESET} ${GREEN}<target>${RESET}'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${YELLOW}%-15s${RESET} %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker image
	docker build -t feedback2me-local .

run: ## Run Docker container with environment variables
	docker run --rm --env-file .env -p 8080:8080 feedback2me-local

stop: ## Stop all running containers for this project
	docker ps -q --filter ancestor=feedback2me-local | xargs -r docker stop

rebuild: ## Rebuild and restart the container
	$(MAKE) build
	$(MAKE) run