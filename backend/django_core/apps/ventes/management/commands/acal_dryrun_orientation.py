"""ACAL58 — DRY-RUN : les devis dont ``_pans_geometry`` changerait.

``extract_roof_config`` lit désormais l'orientation des modules POSÉS
(``geometry.tiltDeg``/``azimuthDeg``) avant la pente du toit
(``orientation_du_pan``). ``_pans_geometry`` et ``etude_params['toiture']`` ne
changent qu'au prochain geste qui les réécrit (création, resynchronisation) :
cette commande liste, AVANT le merge, les devis NON brouillon dont la
géométrie stockée changerait à ce geste — référence / statut / inclinaison et
azimut avant → après — pour la décision du fondateur.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
(et surtout aucun devis envoyé) n'est jamais réécrit ici.

    python manage.py acal_dryrun_orientation [--company <slug>] [--tous]
"""
from django.core.management.base import BaseCommand


def _comparer(devis):
    """``[(label, avant, après), …]`` des pans dont l'orientation changerait."""
    from apps.ventes.services import extract_roof_config

    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else {}
    avant = [p for p in (layout.get('_pans_geometry') or [])
             if isinstance(p, dict)]
    apres = (extract_roof_config(layout) or {}).get('pans') or []
    ecarts = []
    for index, (vieux, neuf) in enumerate(zip(avant, apres), start=1):
        a = (vieux.get('inclinaison_deg'), vieux.get('azimut_deg'))
        b = (neuf.get('inclinaison_deg'), neuf.get('azimut_deg'))
        if a != b:
            ecarts.append((vieux.get('label') or 'Pan %d' % index, a, b))
    return ecarts


class Command(BaseCommand):
    help = ('ACAL58 — liste (lecture seule) les devis dont _pans_geometry '
            'changerait avec la lecture de l\'orientation posée.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--tous', action='store_true', default=False,
            help='Inclure aussi les brouillons (par défaut : NON brouillons).')

    def handle(self, *args, **options):
        from apps.ventes.models import Devis

        qs = (Devis.objects.filter(roof_layout__has_key='_pans_geometry')
              .select_related('company').order_by('company_id', 'reference'))
        if not options.get('tous'):
            qs = qs.exclude(statut=Devis.Statut.BROUILLON)
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        nb = 0
        for devis in qs.iterator():
            ecarts = _comparer(devis)
            if not ecarts:
                continue
            nb += 1
            for label, (inc_a, az_a), (inc_b, az_b) in ecarts:
                self.stdout.write(
                    f'  {devis.company.slug:<20} {devis.reference:<22} '
                    f'{devis.statut:<10} {label} : inclinaison {inc_a} → '
                    f'{inc_b}, azimut {az_a} → {az_b}')
        self.stdout.write(f'Devis concernés : {nb}')
