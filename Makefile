APP_NAME=obsidian-search
IMAGE_NAME=obsidian-search:latest
CONTAINER_NAME=obsidian-search

build:
	docker build -t $(IMAGE_NAME) .

start:
	docker run -d --rm --name $(CONTAINER_NAME) -p 5055:5055 -e VAULT="/vault" -e VAULT_NAME="MyVault" -v $(VAULT):/vault $(IMAGE_NAME)

stop:
	docker stop $(CONTAINER_NAME)

logs:
	docker logs -f $(CONTAINER_NAME)
