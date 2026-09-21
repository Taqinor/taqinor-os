"""NTCON18 — Photo-rapport hebdomadaire d'avancement (Celery beat).

Compile les photos ``records.Attachment`` de la semaine (chantier + réserves
NTCON1 + journal NTCON6) en un PDF « avancement photo » envoyé au client/MOE.

OPT-IN STRICT : seuls les chantiers portant un ``AbonnementRapportPhoto``
``actif=True`` sont traités — aucun envoi n'a jamais lieu par défaut.
KEY-GATED : sans clé email configurée (``ANYMAIL``), la commande est un NO-OP
PROPRE (elle le dit, n'envoie rien, ne lève jamais).

Le PDF ne contient QUE des photos datées — jamais un coût interne, jamais un
prix d'achat (CLAUDE.md).

Le corps du balayage vit dans ``services.envoyer_rapports_photo_hebdo`` —
unique implémentation, partagée par cette commande (à la demande) et par la
tâche planifiée ``btp_chantier.rapport_photo_hebdo``.

Run :
    python manage.py rapport_photo_hebdo [--du AAAA-MM-JJ] [--au AAAA-MM-JJ]
                                         [--chantier ID] [--dry-run]
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError


def _parse_date(valeur, champ):
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        raise CommandError(
            f'{champ} : date invalide « {valeur} » — format attendu '
            'AAAA-MM-JJ.')


class Command(BaseCommand):
    help = (
        "Envoie le photo-rapport hebdomadaire d'avancement aux chantiers "
        'abonnés (opt-in). No-op propre sans clé email configurée.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--du', dest='du', default=None,
            help='Début de période (AAAA-MM-JJ). Défaut : au − 6 jours.')
        parser.add_argument(
            '--au', dest='au', default=None,
            help="Fin de période (AAAA-MM-JJ). Défaut : aujourd'hui.")
        parser.add_argument(
            '--chantier', dest='chantier', type=int, default=None,
            help='Restreindre à un seul chantier (ID).')
        parser.add_argument(
            '--dry-run', dest='dry_run', action='store_true',
            help='Produit les rapports sans rien envoyer.')

    def handle(self, *args, **options):
        from apps.btp_chantier.services import envoyer_rapports_photo_hebdo

        du = _parse_date(options.get('du'), '--du')
        au = _parse_date(options.get('au'), '--au')
        if du and au and du > au:
            raise CommandError(
                '--du : le début de période ne peut pas suivre la fin '
                f'(--au {au}).')

        resultat = envoyer_rapports_photo_hebdo(
            du=du, au=au, chantier_id=options.get('chantier'),
            dry_run=bool(options.get('dry_run')))

        if not resultat['email_configure']:
            self.stdout.write(self.style.WARNING(
                'rapport_photo_hebdo : aucune clé email configurée — '
                'aucun envoi (no-op).'))
        self.stdout.write(self.style.SUCCESS(
            f"rapport_photo_hebdo : {resultat['examines']} chantier(s) "
            f"abonné(s), {resultat['envoyes']} rapport(s) envoyé(s), "
            f"{resultat['sans_photo']} sans photo sur la période."))
