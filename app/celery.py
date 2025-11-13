import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

celery_app = Celery("fx-quotes")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks()


__all__ = ["celery_app"]
