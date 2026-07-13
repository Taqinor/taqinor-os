"""NTSEC17 — Vérifie l'intégrité du chaînage d'inviolabilité du journal d'audit.

Usage : ``manage.py verify_audit_chain <company_id>``. Recalcule le hash de
chaque ligne chaînée de la société et détecte toute rupture (ligne modifiée ou
supprimée). Sort en code 1 si une rupture est trouvée."""
from django.core.management.base import BaseCommand, CommandError

from apps.audit.selectors import verify_audit_chain


class Command(BaseCommand):
    help = "Vérifie le chaînage hash du journal d'audit d'une société."

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=int)

    def handle(self, *args, **options):
        company_id = options['company_id']
        result = verify_audit_chain(company_id)
        if result['ok']:
            self.stdout.write(self.style.SUCCESS(
                'Chaîne intègre : %d lignes vérifiées.'
                % result['checked']))
            return
        broken = result['broken_pk']
        raise CommandError(
            'Rupture de chaîne détectée à la ligne pk=%s '
            '(%d lignes vérifiées avant rupture).'
            % (broken, result['checked']))
