"""ACAL1194 — DRY-RUN : les calepinages dont l'orientation lue des surfaces de
pose CHANGERA avec ACAL921, à montrer au fondateur AVANT.

Tous les écrivains posent une FACE dans ``rowAzimuthDeg`` (180 = sud) ; le
seul lecteur, ``apps/ventes/domain/geometrie.py::pans_du_document``, lit
aujourd'hui ``(valeur + 90) % 360`` (un « 180 » enregistré est lu 270).
ACAL921 corrige le LECTEUR : aucun document n'est faux, c'est sa lecture qui
change. Une ligne par surface orientée :

    calepinage | surface (id, genre) | valeur saisie | face lue aujourd'hui |
    face lue après ACAL921 | devis lié (id, statut)

LECTURE SEULE : aucun calepinage, aucun devis n'est réécrit.

    python manage.py acal_dryrun_azimut_surfaces --dry-run [--company <slug>]
"""
from __future__ import annotations

from collections import Counter

from django.apps import apps as registre
from django.core.management.base import BaseCommand, CommandError

from apps.calepinage.services.valeurs import nombre as _nombre


def ecarts_azimut_surfaces(layout):
    """``[{surface, genre, saisi, face_aujourdhui, face_apres}]`` des surfaces
    de pose à ``rowAzimuthDeg`` numérique. La face d'aujourd'hui recopie la
    règle de ``pans_du_document`` : ``(valeur + 90) % 360`` (jamais importée
    d'apps/ventes) ; après ACAL921, la face est la valeur saisie."""
    surfaces = layout.get('poseSurfaces') if isinstance(layout, dict) else None
    lignes = []
    for index, surface in enumerate(
            surfaces if isinstance(surfaces, list) else []):
        if not isinstance(surface, dict):
            continue
        brut = surface.get('rowAzimuthDeg')
        # Un azimut NUMÉRIQUE seulement : le lecteur recopié ignore un texte.
        saisi = None if isinstance(brut, str) else _nombre(brut)
        if saisi is None:
            continue
        lignes.append({
            'surface': str(surface.get('id') or 'surface-%d' % (index + 1)),
            'genre': str(surface.get('kind') or 'sol'),
            'saisi': saisi,
            'face_aujourdhui': (saisi + 90.0) % 360.0,
            'face_apres': saisi % 360.0,
        })
    return lignes


class Command(BaseCommand):
    help = ('ACAL1194 — liste (lecture seule) les surfaces de pose dont la '
            'face lue changera avec ACAL921.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Obligatoire : la commande ne fait que lire.')
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        if not options.get('dry_run'):
            raise CommandError(
                "ajoutez --dry-run : cette commande n'écrit jamais")
        Calepinage = registre.get_model('calepinage', 'Calepinage')
        qs = (Calepinage.objects.exclude(roof_layout__isnull=True)
              .select_related('devis').order_by('company_id', 'pk'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        ecrire = self.stdout.write
        ecrire('DRY-RUN ACAL1194 (lecture seule) — aucune écriture')
        ecrire("calepinage | surface (id, genre) | valeur saisie | face lue "
               "aujourd'hui | face lue après ACAL921 | devis lié (id, statut)")
        surfaces, calepinages, statuts = 0, 0, Counter()
        for calepinage in qs.iterator(chunk_size=200):
            lignes = ecarts_azimut_surfaces(calepinage.roof_layout)
            if not lignes:
                continue
            calepinages += 1
            devis = calepinage.devis
            lie = '%s (%s)' % (devis.pk, devis.statut) if devis else '—'
            if devis:
                statuts[devis.statut] += 1
            for ligne in lignes:
                surfaces += 1
                ecrire('%s | %s (%s) | %g | %g | %g | %s' % (
                    calepinage.pk, ligne['surface'], ligne['genre'],
                    ligne['saisi'], ligne['face_aujourdhui'],
                    ligne['face_apres'], lie))
        ecrire('%d surface(s) sur %d calepinage(s) concernés.'
               % (surfaces, calepinages))
        ecrire('Devis liés par statut : %s.' % (
            ', '.join('%s %d' % paire for paire in sorted(statuts.items()))
            or 'aucun'))
