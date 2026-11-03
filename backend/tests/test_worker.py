from app.worker.celery_app import celery_app
from app.worker.tasks import ping


def test_ping_task_runs_eagerly() -> None:
    celery_app.conf.task_always_eager = True
    try:
        assert ping.delay().get(timeout=5) == "pong"
    finally:
        celery_app.conf.task_always_eager = False


def test_celery_config() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert str(celery_app.conf.timezone) == "Australia/Sydney"
    assert celery_app.conf.task_acks_late is True
