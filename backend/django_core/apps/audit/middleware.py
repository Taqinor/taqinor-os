"""Middleware d'audit : porte la requête courante dans un thread-local pour que
les signaux CRUD puissent résoudre l'acteur (paresseusement) et savoir qu'on est
bien dans une requête. Ne fait rien d'autre — aucune écriture, aucun coût."""
from . import recorder


class AuditActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        recorder.begin_request(request)
        try:
            return self.get_response(request)
        finally:
            recorder.end_request()
