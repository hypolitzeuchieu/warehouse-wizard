.PHONY: start stop makemigrations migrate start-celery start-runserver check-migrations

UV ?= uv
PYTHON ?= python
PROJECT ?= retailpulse
MANAGE := $(UV) run $(PYTHON) manage.py
CELERY := $(UV) run celery -A $(PROJECT)

PID_DIR := .pids
LOG_DIR := logs
RUNSERVER_PID := $(PID_DIR)/runserver.pid
CELERY_PID := $(PID_DIR)/celery.pid
RUNSERVER_PORT ?= 8000

start: check-migrations migrate start-celery start-runserver
	@echo "All services started. Logs: $(LOG_DIR)/runserver.log, $(LOG_DIR)/celery.log"
	@echo "Use \`make stop\` to stop background processes."

check-migrations:
	@echo "Checking for pending migrations (no files will be created)..."
	@$(MANAGE) makemigrations --check 2>/dev/null || echo "Note: Some migrations may be needed. Run 'make makemigrations' to create them."; true

makemigrations:
	@echo "Running makemigrations..."
	@$(MANAGE) makemigrations

migrate:
	@echo "Running migrations..."
	@$(MANAGE) migrate

start-celery:
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@if [ -f $(CELERY_PID) ] && kill -0 $$(cat $(CELERY_PID)) 2>/dev/null; then \
		echo "Celery worker already running with PID $$(cat $(CELERY_PID))."; \
	else \
		echo "Starting Celery worker..."; \
		nohup $(CELERY) worker --loglevel=info > $(LOG_DIR)/celery.log 2>&1 & echo $$! > $(CELERY_PID); \
		echo "Celery worker started with PID $$(cat $(CELERY_PID))."; \
	fi

start-runserver:
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@if [ -f $(RUNSERVER_PID) ] && kill -0 $$(cat $(RUNSERVER_PID)) 2>/dev/null; then \
		echo "Django server already running with PID $$(cat $(RUNSERVER_PID))."; \
	else \
		echo "Starting Django server on port $(RUNSERVER_PORT)..."; \
		nohup $(MANAGE) runserver 0.0.0.0:$(RUNSERVER_PORT) > $(LOG_DIR)/runserver.log 2>&1 & echo $$! > $(RUNSERVER_PID); \
		echo "Django server started with PID $$(cat $(RUNSERVER_PID))."; \
	fi

stop:
	@echo "Stopping services..."
	@if [ -f $(RUNSERVER_PID) ]; then \
		PID=$$(cat $(RUNSERVER_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping Django server (PID $$PID)..."; \
			kill $$PID; \
			echo "Django server stopped."; \
		else \
			echo "Django server not running (stale PID)."; \
		fi; \
		rm -f $(RUNSERVER_PID); \
	else \
		echo "No Django server PID file found."; \
	fi
	@if [ -f $(CELERY_PID) ]; then \
		PID=$$(cat $(CELERY_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping Celery worker (PID $$PID)..."; \
			kill $$PID; \
			echo "Celery worker stopped."; \
		else \
			echo "Celery worker not running (stale PID)."; \
		fi; \
		rm -f $(CELERY_PID); \
	else \
		echo "No Celery worker PID file found."; \
	fi
	@echo "Services stopped."
