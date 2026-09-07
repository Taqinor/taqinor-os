"""MRY34 — rattrapage : repose une prochaine étape sur les leads « joints »
restés sans aucune étape ouverte.

Avant le filet MRY34, marquer une touche « joint » / « intéressé » arrêtait la
cadence de contact (MRY9) sans rien poser derrière : le lead qu'on venait de
JOINDRE sortait de toutes les files de relance. Cette commande retrouve ces
dossiers (funnel actif, aucune touche ouverte, au moins une issue de succès
dans le chatter) et leur applique le MÊME filet que le récepteur — jamais une
seconde implémentation.

Dry-run PAR DÉFAUT (elle liste, n'écrit rien) ; ``--apply`` applique, borné
par ``--limite`` (défaut 40) pour que la file de Meryem ne déborde jamais
d'un coup — même philosophie de lot que le placement MRY30.
"""
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import assurer_prochaine_etape_apres_succes


class Command(BaseCommand):
    help = ("MRY34 — repose une prochaine étape sur les leads joints/"
            "intéressés restés sans étape ouverte (dry-run par défaut ; "
            "--apply pour écrire, --limite N par passage).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Applique réellement (sinon la commande ne fait que lister).")
        parser.add_argument(
            '--limite', type=int, default=40,
            help="Leads traités au plus par passage (défaut 40).")

    def handle(self, *args, **options):
        ouvertes = RelanceEtape.objects.filter(
            lead=OuterRef('pk'), statut=RelanceEtape.Statut.A_FAIRE)
        # Seule une issue de SUCCÈS saisie par un HUMAIN compte (même règle
        # que le récepteur MRY9) : une ligne système ne décide de rien.
        succes = LeadActivity.objects.filter(
            lead=OuterRef('pk'), user__isnull=False,
            outcome__in=['joint', 'interesse'])
        candidats = (
            Lead.objects
            .filter(perdu=False, is_archived=False)
            .exclude(stage__in=[stages.SIGNED, stages.COLD])
            .annotate(a_ouverte=Exists(ouvertes), a_succes=Exists(succes))
            .filter(a_ouverte=False, a_succes=True)
            .order_by('-id'))
        total = candidats.count()
        limite = max(1, options['limite'])
        lot = list(candidats.select_related('company')[:limite])

        if not options['apply']:
            self.stdout.write(
                f'{total} lead(s) joints sans prochaine étape. Dry-run — '
                f'rien n\'est écrit ; --apply en traiterait {len(lot)} '
                f'(--limite {limite}).')
            for lead in lot:
                self.stdout.write(
                    f'  - #{lead.pk} {lead.nom} ({lead.company.slug}, '
                    f'étape {lead.stage})')
            return

        poses = 0
        for lead in lot:
            # user=None : c'est un rattrapage système, pas un contact humain.
            if assurer_prochaine_etape_apres_succes(lead, None) is not None:
                poses += 1
        restants = max(0, total - poses)
        self.stdout.write(self.style.SUCCESS(
            f'{poses} étape(s) posée(s), {restants} lead(s) restant(s) '
            f'(relancer la commande pour le lot suivant).'))
