"""ACAL1407 + ACAL1501 (D-ACAL-83) — DRY-RUN : la perte d'ombrage proche
mesurée au CENTRE du pan (matrice ``shading12x24`` enregistrée) à côté de
celle mesurée sur les PANNEAUX POSÉS.

Le fondateur a tranché le 23/11/2026 : l'ombre proche se mesure en moyenne
sur les panneaux posés (sans panneau, sur une grille du pan), et « la liste
des calepinages qui changent est montrée avant toute application aux
existants ». Cette commande est cette liste. Elle n'écrit RIEN et n'a AUCUNE
option d'écriture : un calepinage existant garde sa matrice jusqu'à ce que
l'atelier la recalcule (une source d'ombrage ou la pose modifiée).

    société | calepinage | statut | perte avant (centre du pan) → perte après
    (panneaux posés) | écart

« Avant » = la matrice 12 × 24 rangée au document. « Après » = la table
d'ombrage par direction du soleil des modules posés du pan
(``zones[].geometry.shadeTable``, ACAL459 — la part des modules dont le rayon
n'est pas coupé), recomposée en matrice 12 × 24 comme l'atelier le fait
(``tableOmbrage.ts::recomposerMatrice`` : case la plus proche, part diffuse
des heures masquées). Les deux matrices sont réduites à un pourcentage annuel
avec les MÊMES poids : sinus de la hauteur du soleil au milieu de chaque mois
et de chaque heure solaire, multiplié par le nombre de jours du mois — une
mesure de liste, jamais un chiffre imprimé.

Sans table de modules posés (document antérieur au 20/11, pan sans panneau,
ou plusieurs pans à table), « après » n'est pas calculable ici : la ligne le
dit — la grille du pan se calcule dans l'atelier, à la réouverture.

    python manage.py acal_dryrun_ombrage_modules [--company <slug>] [--tous]
"""
from __future__ import annotations

import calendar
import logging

from django.apps import apps as registre
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

#: Part du rayonnement gardée par une heure masquée, CONVENTION DE L'ATELIER
#: (``apps/web/src/lib/shadingEngine.ts::DIFFUSE_FRACTION_WHEN_SHADED``) :
#: c'est la valeur d'une case masquée de ``shading12x24``. Elle sert à
#: recomposer la table dans la même convention que la matrice enregistrée.
PART_DIFFUSE_HEURE_MASQUEE = 0.25

#: Jour du mois où le soleil est placé (milieu du mois, comme l'atelier).
JOUR_MILIEU_DE_MOIS = 15

#: Année de référence du calendrier (non bissextile) : la position du soleil
#: dépend du jour de l'année, pas de l'année.
ANNEE_DE_REFERENCE = 2025

#: Degrés de longitude par heure (passage heure solaire → UTC).
DEGRES_PAR_HEURE = 15.0

#: Écart sous lequel une ligne n'est pas listée (points de pourcentage) —
#: l'arrondi d'affichage au dixième.
ECART_LISTE_POINTS = 0.05


def ecart_ombrage_du_document(document):
    """``{'avant': %, 'apres': % | None, 'motif': str}`` ou ``None``.

    ``None`` : le document ne porte aucune matrice d'ombrage (rien ne peut
    changer). ``apres`` à ``None`` : le motif dit pourquoi il n'est pas
    calculable ici. Fonction PURE.
    """
    from apps.calepinage.services.etapes import ombrage_proche, ombrage_table
    from apps.calepinage.services.valeurs import nombre

    document = document if isinstance(document, dict) else {}
    brute = document.get('shading12x24')
    if brute is None:
        return None
    matrice, refus = ombrage_proche._lire_matrice(brute)
    if refus:
        return {'avant': None, 'apres': None, 'motif': refus}
    epingle = document.get('pin') if isinstance(document.get('pin'), dict) else {}
    lat = nombre(epingle.get('lat'))
    lon = nombre(epingle.get('lng') if epingle.get('lng') is not None
                 else epingle.get('lon'))
    if lat is None or lon is None:
        return {'avant': None, 'apres': None,
                'motif': "document sans épingle (pin.lat / pin.lng) : la "
                         "position du soleil n'est pas calculable"}
    soleils = _soleils(lat, lon)
    avant = _perte_pct(matrice, soleils)
    tables = [zone for zone in (document.get('zones') or [])
              if isinstance(zone, dict) and isinstance(zone.get('geometry'), dict)
              and isinstance(zone['geometry'].get('shadeTable'), dict)]
    if len(tables) != 1:
        motif = ('aucune table des modules posés (document antérieur au '
                 '20/11 ou pan sans panneau) : la grille du pan se calcule '
                 "dans l'atelier, à la réouverture" if not tables else
                 f'{len(tables)} pans portent une table : la matrice '
                 "enregistrée est celle du pan actif, non désigné au document")
        return {'avant': avant, 'apres': None, 'motif': motif}
    table = ombrage_table.table_du_pan({'ombrage': {'layout': document}})
    if table is None:
        return {'avant': avant, 'apres': None,
                'motif': 'table des modules posés illisible : refusée en bloc'}
    return {'avant': avant,
            'apres': _perte_pct(_recomposer(table, soleils), soleils),
            'motif': ''}


def _soleils(lat, lon):
    """``[[(hauteur°, azimut° depuis le nord) | None] × 24] × 12``."""
    from core.calepinage.soleil import position_solaire

    from apps.calepinage.services.etapes.ombrage_table import (
        DEMI_TOUR_DEG, TOUR_DEG)

    lignes = []
    for mois in range(1, 13):
        ligne = []
        for heure in range(24):
            utc = (heure + 0.5 - lon / DEGRES_PAR_HEURE) % 24.0
            soleil = position_solaire(lat, lon, annee=ANNEE_DE_REFERENCE,
                                      mois=mois, jour=JOUR_MILIEU_DE_MOIS,
                                      heure_utc=utc)
            ligne.append(None if soleil.elevation_deg <= 0 else (
                soleil.elevation_deg,
                (soleil.azimut_depuis_sud_deg + DEMI_TOUR_DEG) % TOUR_DEG))
        lignes.append(ligne)
    return lignes


def _recomposer(table, soleils):
    """La table par direction, recomposée en matrice 12 × 24 (convention de l'atelier)."""
    from apps.calepinage.services.etapes.ombrage_table import _plus_proche

    azimuts, hauteurs, facteurs = table
    matrice = []
    for ligne_soleil in soleils:
        ligne = []
        for soleil in ligne_soleil:
            if soleil is None:
                ligne.append(1.0)
                continue
            part = facteurs[_plus_proche(hauteurs, soleil[0], circulaire=False)][
                _plus_proche(azimuts, soleil[1], circulaire=True)]
            ligne.append(part + (1.0 - part) * PART_DIFFUSE_HEURE_MASQUEE)
        matrice.append(ligne)
    return matrice


def _perte_pct(matrice, soleils):
    """Perte annuelle (%) : poids = sinus de la hauteur × jours du mois."""
    import math

    poids_total = perdu = 0.0
    for mois, (ligne, ligne_soleil) in enumerate(zip(matrice, soleils), start=1):
        jours = calendar.monthrange(ANNEE_DE_REFERENCE, mois)[1]
        for facteur, soleil in zip(ligne, ligne_soleil):
            if soleil is None:
                continue
            poids = math.sin(math.radians(soleil[0])) * jours
            poids_total += poids
            perdu += poids * (1.0 - facteur)
    return round(perdu / poids_total * 100.0, 1) if poids_total else 0.0


def _pct(valeur):
    return '—' if valeur is None else f'{valeur:.1f} %'.replace('.', ',')


class Command(BaseCommand):
    help = ("ACAL1407 — liste (lecture seule) la perte d'ombrage proche au "
            'centre du pan et sur les panneaux posés, calepinage par calepinage.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--tous', action='store_true', default=False,
            help='Lister aussi les calepinages dont la perte ne change pas.')

    def handle(self, *args, **options):
        Calepinage = registre.get_model('calepinage', 'Calepinage')
        qs = (Calepinage.objects.exclude(roof_layout__isnull=True)
              .select_related('company').order_by('company_id', 'pk'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        ecrire = self.stdout.write
        ecrire('DRY-RUN ACAL1407 (lecture seule) — aucune écriture.')
        ecrire('société | calepinage | statut | perte avant (centre du pan) '
               '→ perte après (panneaux posés) | écart')
        listes = 0
        for calepinage in qs.iterator(chunk_size=200):
            try:
                ecart = ecart_ombrage_du_document(calepinage.roof_layout)
            except Exception as exc:  # signalé, jamais fatal
                logger.warning('handle : document illisible, ignoré', exc_info=True)
                ecrire(f'  {calepinage.pk} : illisible ({exc})')
                continue
            if ecart is None:
                continue
            avant, apres = ecart['avant'], ecart['apres']
            change = (apres is None or avant is None
                      or abs(apres - avant) >= ECART_LISTE_POINTS)
            if not change and not options.get('tous'):
                continue
            listes += 1
            slug = getattr(calepinage.company, 'slug', '') or ''
            if apres is None or avant is None:
                fin = f'après non calculé ici — {ecart["motif"]}'
            else:
                fin = f'{(apres - avant):+.1f} points'.replace('.', ',')
            ecrire(f'  {slug} | {calepinage.pk} « {calepinage.titre} » | '
                   f'{calepinage.statut} | {_pct(avant)} → {_pct(apres)} | {fin}')
        ecrire(f'Calepinages listés : {listes}')
