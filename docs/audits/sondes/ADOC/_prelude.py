# Prélude commun des sondes ADOC (vérifie 2026-10-09) : mail en mémoire, Celery coupé, HTTP sortant bloqué,
# tout dans une transaction ANNULÉE. Rejouable : docker exec -i <django> python manage.py shell < (prélude + sonde).
from django.conf import settings
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
from django.core import mail
mail.outbox = []
from celery import current_app
current_app.conf.task_always_eager = False
_CELERY_CALLS = []
from celery.app.task import Task
Task.apply_async = lambda self, *a, **k: _CELERY_CALLS.append(self.name)
Task.delay = lambda self, *a, **k: _CELERY_CALLS.append(self.name)
import socket
_orig_connect = socket.socket.connect
def _guard(self, addr, *a, **k):
    host = addr[0] if isinstance(addr, tuple) else str(addr)
    if host not in ('db', 'redis', 'redis_cache', 'minio', '127.0.0.1', 'localhost') and not str(host).startswith('172.'):
        raise RuntimeError(f'HTTP sortant bloqué par la sonde : {host}')
    return _orig_connect(self, addr, *a, **k)
socket.socket.connect = _guard
from django.db import transaction
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
class R(Exception):
    pass
