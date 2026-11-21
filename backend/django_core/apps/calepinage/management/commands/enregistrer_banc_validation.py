"""ACAL474 — enregistre les réponses PVGIS RÉELLES du banc de validation.

Outil MANUEL (réseau, une fois) : pour chaque site marocain du banc, il
appelle l'API publique PVGIS ``seriescalc`` DEUX fois — ``pvcalculation=1``
(PVGIS calcule la production : ``peakpower=1``, ``loss`` = somme des postes,
7,25 %) puis ``pvcalculation=0`` (irradiance seule) — pour la MÊME année et le
MÊME plan (15°, plein sud), et écrit chaque réponse telle qu'elle est revenue
sous ``tests/fixtures_pvgis/``. Comme les fixtures de Casablanca (CALX195),
seules les lignes du 15 de chaque mois sont gardées (288 sur 8784) : le
fichier reste une réponse RÉELLE, jamais une série fabriquée.

Aucun chiffre n'est écrit à la main : les coordonnées viennent de
``apps/parametres/villes_maroc.py::coordonnees_ville`` et la provenance (URL,
date) est inscrite dans ``_provenance``. Casablanca garde ses fixtures
existantes (33,5 / −7,6, enregistrées par CALX195) et n'est pas ré-appelée.

    python manage.py enregistrer_banc_validation [--sites marrakech oujda agadir]
                                                 [--annee 2020]

La mesure elle-même (``banc_validation.json``) se régénère ensuite, à la main
et en nommant le changement de modèle voulu :
``python -m apps.calepinage.tests.test_calx195_validation --write``.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from apps.parametres.villes_maroc import coordonnees_ville

DOSSIER = (pathlib.Path(__file__).resolve().parents[2] / 'tests'
           / 'fixtures_pvgis')
URL = 'https://re.jrc.ec.europa.eu/api/v5_3/seriescalc'

#: Les sites enregistrés par cette commande (Casablanca l'est déjà).
SITES = ('marrakech', 'oujda', 'agadir')

#: Le plan du banc : celui des fixtures de Casablanca (CALX195).
ANGLE = 15
AZIMUT = 0
JOUR_GARDE = 15
#: La réponse de Casablanca (CALX195) d'où la perte du banc est LUE (CAL238).
REFERENCE_CASABLANCA = DOSSIER / 'seriescalc_casablanca_sud.json'

TRONCATURE = ("seules les lignes du 15 de chaque mois sont gardées (288 "
              "lignes réelles sur 8784) : le fichier reste une réponse RÉELLE, "
              "jamais une série fabriquée.")


def _perte_du_banc():
    """La somme des postes que PVGIS a reçue pour Casablanca (CALX195),
    lue dans sa réponse enregistrée — jamais recopiée (CAL238)."""
    reponse = json.loads(REFERENCE_CASABLANCA.read_text(encoding='utf-8'))
    return reponse['inputs']['pv_module']['system_loss']


def _requete(lat, lon, annee, *, production):
    parametres = {
        'lat': lat, 'lon': lon, 'startyear': annee, 'endyear': annee,
        'pvcalculation': 1 if production else 0, 'angle': ANGLE,
        'aspect': AZIMUT, 'raddatabase': 'PVGIS-SARAH3',
        'outputformat': 'json',
    }
    if production:
        parametres.update(peakpower=1, loss=_perte_du_banc(), pvtechchoice='crystSi',
                          mountingplace='building')
    return '%s?%s' % (URL, urllib.parse.urlencode(parametres))


def _tronquer(reponse):
    lignes = reponse['outputs']['hourly']
    reponse['outputs']['hourly'] = [
        ligne for ligne in lignes
        if int(ligne['time'][6:8]) == JOUR_GARDE]
    return reponse


class Command(BaseCommand):
    help = ("Enregistre les réponses PVGIS réelles (avec et sans production) "
            "des sites du banc de validation ACAL474.")

    def add_arguments(self, parser):
        parser.add_argument('--sites', nargs='+', default=list(SITES),
                            choices=SITES)
        parser.add_argument('--annee', type=int, default=2020)

    def handle(self, *args, **options):
        aujourd_hui = datetime.date.today().isoformat()
        for site in options['sites']:
            coordonnees = coordonnees_ville(site)
            if coordonnees is None:
                raise CommandError(
                    "Aucune coordonnée pour « %s » dans villes_maroc." % site)
            lat, lon = (round(valeur, 4) for valeur in coordonnees)
            for production, suffixe in ((True, ''), (False, '_irradiance')):
                url = _requete(lat, lon, options['annee'],
                               production=production)
                with urllib.request.urlopen(url, timeout=120) as flux:
                    reponse = json.loads(flux.read().decode('utf-8'))
                reponse = _tronquer(reponse)
                reponse['_provenance'] = {
                    'enregistre_le': aujourd_hui, 'url': url,
                    'reponse': "RÉELLE — réponse PVGIS v5_3 telle qu'elle est "
                               "revenue",
                    'troncature': TRONCATURE,
                }
                chemin = DOSSIER / ('seriescalc_%s_sud%s.json' % (site, suffixe))
                chemin.write_text(json.dumps(reponse, ensure_ascii=False),
                                  encoding='utf-8')
                self.stdout.write('%s : %d lignes -> %s' % (
                    site, len(reponse['outputs']['hourly']), chemin.name))
