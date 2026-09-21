"""NTHCM19 — rappels des parcours de formation OBLIGATOIRES non terminés.

Parcourt les sociétés ACTIVES (``authentication.selectors.active_companies``,
SCA19 : un tenant suspendu ne relance plus personne) et notifie l'EMPLOYÉ
lui-même dès qu'un parcours ``obligatoire`` lui est assigné depuis plus de
``ReglageRH.rappel_parcours_apres_jours`` jours (défaut 14) sans être terminé.

QUI est notifié : l'employé, via son compte utilisateur. Un dossier SANS compte
applicatif n'est pas notifiable — il est compté et signalé, jamais silencieux.

IDEMPOTENCE (« ne spamme pas »). ``notify`` ne déduplique pas lui-même : on
vérifie donc, avant d'émettre, qu'aucune ``Notification`` du même
``event_type`` portant le même ``link`` stable (``/rh/portail?parcours=<id>``)
n'a déjà été créée AUJOURD'HUI pour ce destinataire — deux exécutions le même
jour ne relancent jamais deux fois la même personne sur le même parcours.
C'est le patron déjà en place dans ``apps/rh/tasks.py`` (YHIRE8).

TYPE D'ÉVÉNEMENT. On réutilise une clé EXISTANTE du référentiel notifications
(``annonce_read_reminder`` — « Relance lecture obligatoire », la sémantique la
plus proche : une obligation à accomplir qu'on relance) plutôt que d'en créer
une nouvelle : ``apps/notifications`` n'appartient pas à cette app, et la
frontière inter-apps se traverse par le service public ``notify``, jamais par
un écrit dans les modèles du voisin.

Planifiée par Celery beat (``rh.rappels_parcours_formation``, quotidien) —
l'enveloppe vit dans ``apps/rh/tasks.py``.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

# Clé EXISTANTE du référentiel notifications (voir docstring) — aucun nouveau
# type d'événement n'est introduit par cette commande.
_EVENT_TYPE = 'annonce_read_reminder'


def _lien_parcours(progression):
    """Lien stable, clé de déduplication quotidienne du rappel."""
    return f'/rh/portail?parcours={progression.parcours_id}'


def progressions_en_retard(company, *, aujourdhui, delai_jours):
    """Progressions OBLIGATOIRES non terminées, assignées depuis > delai_jours.

    Pure et déterministe : la date du jour est passée par l'appelant, jamais
    lue ici.
    """
    from datetime import timedelta

    from apps.rh.models import ProgressionParcours

    limite = aujourdhui - timedelta(days=delai_jours)
    return list(
        ProgressionParcours.objects.filter(
            company=company,
            parcours__obligatoire=True,
            parcours__actif=True,
            created_at__date__lte=limite,
        ).exclude(
            statut=ProgressionParcours.Statut.TERMINE,
        ).select_related('parcours', 'employe', 'employe__user')
    )


def _delai_societe(company, defaut=14):
    """``ReglageRH.rappel_parcours_apres_jours`` de la société (défaut 14)."""
    from apps.rh.models import ReglageRH

    reglage = ReglageRH.objects.filter(company=company).first()
    if reglage is None:
        return defaut
    return reglage.rappel_parcours_apres_jours or defaut


class Command(BaseCommand):
    help = (
        'NTHCM19 — relance les employés dont un parcours de formation '
        'obligatoire reste non terminé au-delà du délai société.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Par défaut : toutes les '
                 'sociétés actives.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Calcule et journalise sans émettre de notification.')

    def handle(self, *args, **options):
        # Import fonction-local du service partagé : frontière cross-app
        # respectée (jamais d'import des modèles/vues de notifications).
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        from authentication.selectors import active_companies

        company_id = options['company']
        dry_run = options['dry_run']
        aujourdhui = timezone.localdate()

        companies = list(active_companies())  # SCA19
        if company_id is not None:
            companies = [c for c in companies if c.pk == company_id]

        total_retard = 0
        total_notifs = 0
        total_sans_compte = 0
        for company in companies:
            delai = _delai_societe(company)
            retards = progressions_en_retard(
                company, aujourdhui=aujourdhui, delai_jours=delai)
            if not retards:
                continue
            total_retard += len(retards)
            self.stdout.write(
                f'{company} : {len(retards)} parcours obligatoire(s) en '
                f'retard (délai {delai} j)')
            if dry_run:
                continue
            for progression in retards:
                destinataire = getattr(progression.employe, 'user', None)
                if destinataire is None:
                    total_sans_compte += 1
                    continue
                lien = _lien_parcours(progression)
                deja = Notification.objects.filter(
                    event_type=_EVENT_TYPE, link=lien,
                    recipient_id=destinataire.id,
                    created_at__date=aujourdhui,
                ).exists()
                if deja:
                    continue
                titre = (
                    f'Formation obligatoire à terminer : '
                    f'{progression.parcours.titre}')[:255]
                corps = (
                    f'Avancement {progression.pourcentage} %. '
                    'Ce parcours vous a été assigné et reste à compléter.')
                try:
                    notify(
                        destinataire, _EVENT_TYPE, titre, body=corps,
                        link=lien, company=company)
                    total_notifs += 1
                except Exception as exc:  # pragma: no cover - défensif
                    self.stderr.write(
                        f'Notification échouée vers {destinataire} : {exc}')

        if total_sans_compte:
            self.stdout.write(
                f'{total_sans_compte} employé(s) sans compte applicatif : '
                'non notifiable(s).')
        self.stdout.write(self.style.SUCCESS(
            f'{total_retard} parcours en retard, '
            f'{total_notifs} rappel(s) émis.'))
