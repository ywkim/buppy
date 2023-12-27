from celery_tasks.proactive_messaging_task import create_proactive_message_task
from config.celery_config import CeleryWorkerConfig

app_config = CeleryWorkerConfig()
app_config.load_config()
celery_app = app_config.initialize_celery_app("proactive_messaging_task")

create_proactive_message_task(celery_app)
