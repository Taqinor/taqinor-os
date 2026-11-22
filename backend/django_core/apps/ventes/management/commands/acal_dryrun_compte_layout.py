"""ACAL59 (C-ACAL-035, C-ACAL-118) — DRY-RUN : les devis NON brouillon dont
le compte lu sur leur layout change avec ``pans_du_document``.

``lire_layout`` additionne désormais TOUS les pans posés (toit + champ au sol
/ ombrière / façade), n'ajoute plus jamais le ``result`` racine aux zones et
ne lit plus ``neededPanels`` comme un compte posé. Les lignes d'un devis ne
changent qu'au prochain geste (génération / resynchronisation) : cette
commande liste, AVANT le merge, les devis non brouillon concernés —
référence / statut / compte avant → après / lignes panneau / ``layout_stale``
actuel du badge et du PDF — pour la décision du fondateur.

« Avant » = la chaîne de lecture HISTORIQUE, FIGÉE ci-dessous telle qu'elle
était sur main (``result`` racine, puis somme des pans de toit avec repli
``neededPanels``, puis surfaces de pose seulement si le toit est muet).

``--pans-existants`` (Critique D1, 22/11) : les devis non brouillon dont le
layout porte une zone ``existant: true`` (ACAL573 — modules déjà en place),
avec le nombre de ces modules : la lecture corrigée (``pans_vendus``) les
retire du compte du devis et des cartes de taille de la page publique.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
(et surtout aucun devis envoyé) n'est jamais réécrit ici.

    python manage.py acal_dryrun_compte_layout [--company <slug>] [--tous]
        [--pans-existants]
"""
from django.core.management.base import BaseCommand


def _compte_historique(layout):
    """La lecture d'AVANT ACAL59 (figée, lecture seule)."""
    layout = layout if isinstance(layout, dict) else {}
    result = layout.get('result') or {}
    compte = int(result.get('panels') or result.get('count') or 0)
    if compte > 0:
        return compte
    zones = (layout.get('areas') or layout.get('zones')
             or layout.get('pans') or [])
    for zone in zones if isinstance(zones, list) else []:
        if not isinstance(zone, dict):
            continue
        res = zone.get('result') or {}
        geo = zone.get('geometry') if isinstance(zone.get('geometry'),
                                                 dict) else {}
        compte += int(res.get('count') or geo.get('count')
                      or zone.get('neededPanels') or 0)
    if compte > 0:
        return compte
    for surface in layout.get('poseSurfaces') or []:
        if isinstance(surface, dict) and isinstance(surface.get('engine'),
                                                    dict):
            try:
                compte += int(round(float(
                    surface['engine'].get('modules') or 0)))
            except (TypeError, ValueError):
                continue
    return compte


def _modules_existants(layout):
    """Critique D1 — les modules des pans « existant » d'un layout (0 sans)."""
    from apps.ventes.domain.geometrie import pans_du_document

    return sum(int(p.get('modules') or 0) for p in pans_du_document(
        layout if isinstance(layout, dict) else {}) if p.get('existant'))


class Command(BaseCommand):
    help = ('ACAL59 — liste (lecture seule) les devis non brouillon dont le '
            'compte lu sur le layout change avec pans_du_document.')

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
        parser.add_argument(
            '--pans-existants', action='store_true', default=False,
            help='Critique D1 : seulement les devis dont une zone est « existant ».')

    def _pans_existants(self, qs):
        from apps.ventes.domain.geometrie import lire_layout

        qs = qs.filter(roof_layout__zones__contains=[{'existant': True}])
        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write('société | référence | statut | modules des pans existants | compte lu')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            existants = _modules_existants(devis.roof_layout)
            if not existants:
                continue
            nb += 1
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | {devis.statut} | '
                f'{existants} | {lire_layout(devis.roof_layout).compte}')
        self.stdout.write(f'Devis concernés : {nb}')

    def handle(self, *args, **options):
        from apps.ventes.domain.dimensionnement_devis import (
            comptes_panneaux_valides)
        from apps.ventes.domain.geometrie import lire_layout
        from apps.ventes.models import Devis
        from apps.ventes.selectors import peremption_layout_devis

        qs = (Devis.objects.exclude(roof_layout__isnull=True)
              .select_related('company').prefetch_related('lignes__produit')
              .order_by('company_id', 'reference'))
        if not options.get('tous'):
            qs = qs.exclude(statut=Devis.Statut.BROUILLON)
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])
        if options.get('pans_existants'):
            return self._pans_existants(qs)

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | référence | statut | compte avant → après | lignes '
            'panneau | layout_stale (badge = PDF)')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            layout = devis.roof_layout
            if not isinstance(layout, dict) or not layout:
                continue
            avant = _compte_historique(layout)
            apres = lire_layout(layout).compte
            if avant == apres:
                continue
            nb += 1
            lignes = sorted(comptes_panneaux_valides(devis))
            stale = peremption_layout_devis(devis).get('layout_stale')
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | '
                f'{devis.statut} | {avant} → {apres} | {lignes} | {stale}')
        self.stdout.write(f'Devis concernés : {nb}')
