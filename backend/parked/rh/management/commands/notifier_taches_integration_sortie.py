"""NTHCM25 — rappels quotidiens des tâches d'on/offboarding EN RETARD.

NTHCM23/24 assignent chaque tâche à un acteur précis (RH, manager, IT,
l'employé) avec sa propre échéance — mais personne n'était prévenu. Deux
moments de notification, deux responsabilités :

1. À L'ASSIGNATION — ``services.notifier_tache_assignee`` (appelée par
   ``instancier_integration`` et par la création d'une tâche de sortie) :
   l'acteur est prévenu UNE fois, tout de suite, best-effort.
2. AU RETARD — cette commande : un rappel QUOTIDIEN tant que la tâche
   échue n'est pas faite.

IDEMPOTENCE (« jamais 2 rappels le même jour pour la même tâche »). ``notify``
ne déduplique pas : on vérifie donc qu'aucune ``Notification`` du même
``event_type`` et du même ``link`` stable n'a déjà été créée AUJOURD'HUI pour
ce destinataire (patron YHIRE8, partagé avec
``services.notifier_tache_assignee``). Deux exécutions le même jour ne
relancent donc jamais deux fois la même personne sur la même tâche.

Une tâche NON ASSIGNÉE (IT sans contact configuré, manager sans compte) n'est
notifiable par personne : elle est comptée et signalée en sortie de commande,
jamais silencieuse.

Planifiée par Celery beat (``rh.notifier_taches_integration_sortie``,
quotidien) — l'enveloppe vit dans ``apps/rh/tasks.py``.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.rh import services


def taches_integration_en_retard(company, *, aujourdhui):
    """Tâches d'intégration échues, non faites, assignées à quelqu'un."""
    from apps.rh.models import ElementIntegrationEmploye

    return list(
        ElementIntegrationEmploye.objects.filter(
            company=company, fait=False, echeance__lt=aujourdhui,
        ).select_related('employe', 'assigne_a').order_by('echeance', 'id'))


def taches_sortie_en_retard(company, *, aujourdhui):
    """Tâches de sortie échues, non récupérées, assignées à quelqu'un."""
    from apps.rh.models import ElementSortie

    return list(
        ElementSortie.objects.filter(
            company=company, recupere=False, echeance__lt=aujourdhui,
        ).select_related('employe', 'assigne_a').order_by('echeance', 'id'))


class Command(BaseCommand):
    help = (
        "NTHCM25 — relance quotidiennement les acteurs dont une tâche "
        "d'intégration ou de sortie est échue et non faite.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Par défaut : toutes les '
                 'sociétés actives.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Calcule et journalise sans émettre de notification.')

    def handle(self, *args, **options):
        from authentication.selectors import active_companies

        company_id = options['company']
        dry_run = options['dry_run']
        aujourdhui = timezone.localdate()

        companies = list(active_companies())  # SCA19
        if company_id is not None:
            companies = [c for c in companies if c.pk == company_id]

        total_retard = 0
        total_rappels = 0
        total_non_assignees = 0
        for company in companies:
            lots = (
                (taches_integration_en_retard(company, aujourdhui=aujourdhui),
                 services.lien_tache_onboarding, "d’intégration"),
                (taches_sortie_en_retard(company, aujourdhui=aujourdhui),
                 services.lien_tache_offboarding, 'de sortie'),
            )
            for taches, lien_de, libelle_famille in lots:
                if not taches:
                    continue
                total_retard += len(taches)
                self.stdout.write(
                    f'{company} : {len(taches)} tâche(s) {libelle_famille} '
                    'en retard')
                if dry_run:
                    continue
                for tache in taches:
                    if tache.assigne_a_id is None:
                        total_non_assignees += 1
                        continue
                    jours = (aujourdhui - tache.echeance).days
                    titre = (
                        f'En retard — tâche {libelle_famille} : '
                        f'{tache.libelle}')
                    corps = (
                        f'Échéance dépassée de {jours} jour(s) '
                        f'({tache.echeance.isoformat()}). '
                        f'Employé : {tache.employe.matricule}.')
                    if services.notifier_tache_assignee(
                            tache, lien=lien_de(tache), titre=titre,
                            corps=corps,
                            event_type=services.EVENT_TACHE_RAPPEL,
                            aujourdhui=aujourdhui):
                        total_rappels += 1

        if total_non_assignees:
            self.stdout.write(
                f'{total_non_assignees} tâche(s) en retard NON ASSIGNÉE(S) : '
                'aucun acteur à relancer (contact IT ou manager à configurer).')
        self.stdout.write(self.style.SUCCESS(
            f'{total_retard} tâche(s) en retard, '
            f'{total_rappels} rappel(s) émis.'))
