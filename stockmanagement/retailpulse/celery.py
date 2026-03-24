from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "retailpulse.settings")

app = Celery("retailpulse")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Explicitly discover tasks from the tasks package
app.autodiscover_tasks(packages=["tasks"])
