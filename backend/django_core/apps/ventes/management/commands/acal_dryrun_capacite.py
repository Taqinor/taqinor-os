"""ACAL272 (C-ACAL-116) — DRY-RUN : les devis ENVOYÉS dont la carte « Max »
(contenance du toit) change.

La contenance respecte désormais les retraits SAISIS (``setbacksM``), le
dégagement PROPRE d'un obstacle (``degagementM``), refuse d'étendre devant une
zone INTERDITE/RÉSERVÉE, une allée de circulation ou un obstacle non
rectangulaire, et compte les surfaces de pose. Cette commande liste, AVANT le
merge, les devis envoyés dont la carte Max change — avant → après — pour la
décision du fondateur.

« Avant » = la même contenance calculée sur une COPIE du document privée des
clés que l'ancien estimateur ignorait (retraits, exclusions, allée, surfaces
de pose, dégagement / forme des obstacles) : c'est exactement ce qu'il voyait.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
n'est réécrit.

    python manage.py acal_dryrun_capacite [--company <slug>] [--tous]
"""
import copy

from django.core.management.base import BaseCommand

#: Les clés que l'estimateur d'AVANT ACAL272 ne lisait pas.
_CLES_IGNOREES_AVANT = ('setbacksM', 'exclusionZones', 'alleeTechnique',
                        'poseSurfaces')
_CLES_OBSTACLE_IGNOREES_AVANT = ('degagementM', 'forme', 'rayonM', 'contour')


def document_d_avant(layout):
    """Le document tel que l'ancien estimateur le voyait (copie)."""
    avant = copy.deepcopy(layout) if isinstance(layout, dict) else {}
    for cle in _CLES_IGNOREES_AVANT:
        avant.pop(cle, None)
    for zone in avant.get('zones') or []:
        if not isinstance(zone, dict):
            continue
        for obstacle in zone.get('obstacles') or []:
            if isinstance(obstacle, dict):
                for cle in _CLES_OBSTACLE_IGNOREES_AVANT:
                    obstacle.pop(cle, None)
    return avant


class Command(BaseCommand):
    help = ('ACAL272 — liste (lecture seule) les devis envoyés dont la '
            'contenance du toit (carte Max) change.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--tous', action='store_true', default=False,
            help='Tous les statuts (par défaut : ENVOYÉS seulement).')

    def handle(self, *args, **options):
        from apps.ventes import calepinage_options as co
        from apps.ventes.models import Devis

        qs = (Devis.objects.exclude(roof_layout__isnull=True)
              .select_related('company').order_by('company_id', 'reference'))
        if not options.get('tous'):
            qs = qs.filter(statut=Devis.Statut.ENVOYE)
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | référence | statut | contenance avant → après | motif')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            layout = devis.roof_layout
            if not isinstance(layout, dict) or not layout:
                continue
            libres = co._modes_libres(devis)
            try:
                avant_doc = document_d_avant(layout)
                avant = co.capacite_du_layout(avant_doc, libres,
                                              contraintes=avant_doc)
                apres = co.capacite_du_layout(layout, libres,
                                              contraintes=layout)
            except Exception as exc:  # noqa: BLE001 — signalé, jamais fatal
                self.stdout.write(f'  {devis.reference} : illisible ({exc})')
                continue
            if avant == apres:
                continue
            nb += 1
            motif = co.motif_non_extensible(layout) or ''
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | '
                f'{devis.statut} | {avant} → {apres} | {motif}')
        self.stdout.write(f'Devis concernés : {nb}')
