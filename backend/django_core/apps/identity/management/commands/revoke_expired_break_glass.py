"""NTSEC22 — Révoque les accès break-glass échus (nettoyage périodique).

Idempotent : restaure le rôle antérieur et horodate la révocation pour chaque
octroi dont l'échéance est passée et qui n'est pas déjà révoqué."""
from django.core.management.base import BaseCommand

from apps.identity.breakglass import revoke_expired


class Command(BaseCommand):
    help = "Révoque les accès break-glass arrivés à échéance."

    def handle(self, *args, **options):
        n = revoke_expired()
        self.stdout.write(self.style.SUCCESS(
            '%d accès break-glass révoqués.' % n))
