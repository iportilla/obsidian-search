# Makefile
IMAGE ?= obsidian-search:latest
NAME  ?= obsidian-search
PORT  ?= 5055

# Your host vault folder (or its parent) that you bind into the container at /vault
VAULT ?= $(PWD)/vault

# 0 = safe (root-limited to /vault), 1 = allow browsing any path (in container FS)
ALLOW_ANY ?= 0

# Obsidian deep-link config:
# If you know your Obsidian vault display name, set VAULT_NAME to enable vault+file links.
VAULT_NAME ?=
# These prefixes translate container paths -> host paths for obsidian://open?path=
CONTAINER_PREFIX ?= /vault
HOST_PREFIX ?= $(VAULT)

.PHONY: build start start-safe start-any stop restart logs shell rm clean rebuild run-local

build:
	docker build -t $(IMAGE) .

start:
	@mkdir -p "$(VAULT)"
	docker run -d --name $(NAME) 		-e BROWSE_ROOT=/vault 		-e ALLOW_ANY_PATH=$(ALLOW_ANY) 		-e OBSIDIAN_CONTAINER_PREFIX="$(CONTAINER_PREFIX)" 		-e OBSIDIAN_HOST_PREFIX="$(HOST_PREFIX)" 		-e OBSIDIAN_VAULT_NAME="$(VAULT_NAME)" 		-p $(PORT):5055 		-v "$(VAULT)":/vault 		$(IMAGE)
	@echo "Started: http://127.0.0.1:$(PORT)"
	@echo "Browse root in container: /vault"
	@echo "ALLOW_ANY_PATH=$(ALLOW_ANY) (0=safe, 1=any path)"
	@echo "Obsidian deep-link mode: $$([ -n '$(VAULT_NAME)' ] && echo 'vault+file' || echo 'absolute path')"

start-safe:
	@$(MAKE) start ALLOW_ANY=0

start-any:
	@$(MAKE) start ALLOW_ANY=1

stop:
	- docker stop $(NAME) >/dev/null 2>&1 || true
	- docker rm $(NAME)   >/dev/null 2>&1 || true
	@echo "Stopped and removed: $(NAME)"

restart: stop start

logs:
	docker logs -f $(NAME)

shell:
	docker exec -it $(NAME) /bin/bash

rm:
	- docker rm -f $(NAME)

clean: stop
	- docker rmi $(IMAGE)

rebuild: clean build

# Run locally without Docker
# Override variables as needed:
#   make run-local HOST_PREFIX="/Users/you/ObsidianVault" VAULT_NAME="My Vault"
run-local:
	@echo "Running locally on http://127.0.0.1:$(PORT)"
	ALLOW_ANY_PATH=$(ALLOW_ANY) 	BROWSE_ROOT="$(VAULT)" 	OBSIDIAN_CONTAINER_PREFIX="$(CONTAINER_PREFIX)" 	OBSIDIAN_HOST_PREFIX="$(HOST_PREFIX)" 	OBSIDIAN_VAULT_NAME="$(VAULT_NAME)" 	python3 obsidian_search.py --host 127.0.0.1 --port $(PORT) 		--browse-root "$(VAULT)" 		--container-prefix "$(CONTAINER_PREFIX)" 		--host-prefix "$(HOST_PREFIX)" 		--vault-name "$(VAULT_NAME)" 		$(if $(filter 1,$(ALLOW_ANY)),--allow-any-path,)
