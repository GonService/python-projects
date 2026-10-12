.PHONY: up demo down test

up: ## Start web + PostgreSQL on http://localhost:8000/admin
	docker compose up -d --build --wait

demo: ## Create admin/admin and sample tickets (local demo only)
	docker compose exec web python manage.py seed_demo

down:
	docker compose down

test:
	python manage.py test
