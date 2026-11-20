.PHONY: migrate seed-demo

migrate:
	./tools/manage-api.sh migrate

seed-demo:
	./tools/manage-api.sh seed_demo
