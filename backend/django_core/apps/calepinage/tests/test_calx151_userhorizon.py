# -*- coding: utf-8 -*-
"""CALX151 — notre horizon part vers PVGIS, et le bloc DIT lequel fait foi.

CE QUI EST PROUVÉ ICI
---------------------
1. **Le profil part** : l'URL porte ``userhorizon`` avec AUTANT de valeurs que
   le profil réel de ``fixtures_pvgis/printhorizon_casablanca.json`` en
   contient (49), et ``usehorizon=1``.
2. **Il part dans le bon sens** : la liste commence au NORD et tourne dans le
   sens HORAIRE — le format que PVGIS documente (« Starting at north and
   moving clockwise »), qui n'est PAS l'échantillonnage de ``printhorizon``.
   Un profil à 24 directions (celles de la fixture qui tombent sur un
   multiple de 15°) le montre sans interpolation : la valeur d'index 6 est
   celle de l'EST et celle d'index 18 celle de l'OUEST.
3. **Le rééchantillonnage conserve la hauteur AU SUD** : exactement quand les
   directions coïncident (profil à 24 points), et à 0,10° près sur le profil
   réel à 49 points (mesuré le 21/09/2026 ; 0,2° est un SEUIL DE TEST, aucune
   valeur métier n'en dépend).
4. **Les trois cas sont exclusifs et publiés** : ``profil_mesure`` /
   ``saisie`` (profil transmis), ``dem_pvgis`` (PVGIS calcule le sien),
   ``aucun`` (``usehorizon=0``, masque déjà dans la géométrie 3D). Fournir
   un profil ET déclarer la géométrie est REFUSÉ.
5. **Un profil troué est REFUSÉ en nommant l'azimut manquant** : un secteur
   non relevé se lirait « dégagé ».

POURQUOI LE BLOC NE CROIT PAS LA RÉPONSE
-----------------------------------------
Vérifié en direct le 21/09/2026 : une réponse ``seriescalc`` à laquelle on
envoie ``userhorizon`` continue d'annoncer ``horizon_data: "DEM-calculated"``
dans ses ``inputs``, alors que le masque envoyé est bel et bien appliqué
(G(i) de midi le 15 janvier au point 33,5 / −7,6 : 793,86 W/m² sans profil,
105,23 W/m² avec un mur de 40° tout autour). Le bloc publie donc CE QUE NOUS
AVONS ENVOYÉ, jamais le champ de la réponse.

AUCUN RÉSEAU, AUCUNE BASE — ``SimpleTestCase``, fixtures réelles rejouées.

Run :
    python manage.py test apps.calepinage.tests.test_calx151_userhorizon
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse

from django.test import SimpleTestCase

from apps.calepinage.services.horizon import (
    lire_profil, profil_saisi, reechantillonner_pour_pvgis,
)
from apps.calepinage.services.pvgis_serie import (
    ClientPvgis, EntreeInvalide, _Cache,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Seuil de TEST pour la hauteur au sud après rééchantillonnage du profil
#: réel à 49 points (écart mesuré le 21/09/2026 : 0,10°).
TOLERANCE_SUD_DEG = 0.2


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


def profil_reel():
    """Le profil PVGIS réel de Casablanca, tel que ``lire_profil`` le rend."""
    return lire_profil(charger('printhorizon_casablanca.json'))


def profil_24_directions():
    """Le MÊME profil réel, réduit aux directions multiples de 15°.

    Aucune hauteur n'est fabriquée : ce sont les hauteurs relevées par PVGIS,
    prises une sur deux. 24 directions tombent pile sur les 24 azimuts
    équidistants que PVGIS rééchantillonnera — la conversion est alors une
    IDENTITÉ, et le test n'a plus à tolérer d'interpolation.
    """
    complet = profil_reel()
    vus = {}
    for point in complet['points']:
        azimut = point['azimut_face_deg'] % 360.0
        if abs(azimut % 15.0) < 1e-9:
            vus[azimut] = max(point['hauteur_deg'], vus.get(azimut, -90.0))
    return dict(complet, points=[
        {'azimut_face_deg': azimut, 'hauteur_deg': hauteur}
        for azimut, hauteur in sorted(vus.items())])


def hauteur_a(profil, azimut_face):
    return [point['hauteur_deg'] for point in profil['points']
            if abs(point['azimut_face_deg'] % 360.0 - azimut_face) < 1e-9][0]


class TransportEnregistre:
    def __init__(self, charge=None):
        self.charge = charge
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return 200, json.dumps(self.charge or {})


def appeler(**extra):
    """Un appel d'irradiance rejoué — rend ``(resultat, params de l'URL)``."""
    transport = TransportEnregistre(
        charger('seriescalc_casablanca_sud_irradiance.json'))
    client = ClientPvgis(transport, cache=_Cache(), dormir=lambda _s: None)
    params = dict(lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
                  annee_debut=2020, annee_fin=2020,
                  obtenue_le='2026-09-21T09:00:00Z')
    params.update(extra)
    resultat = client.serie_irradiance(**params)
    envoyes = urllib.parse.parse_qs(
        urllib.parse.urlparse(transport.appels[0]).query)
    return resultat, envoyes


class LeProfilPart(SimpleTestCase):
    """L'URL porte NOTRE masque, au format documenté par PVGIS."""

    def test_userhorizon_porte_autant_de_valeurs_que_le_profil(self):
        profil = profil_reel()
        _resultat, envoyes = appeler(horizon=profil)
        valeurs = envoyes['userhorizon'][0].split(',')
        self.assertEqual(len(valeurs), len(profil['points']))
        self.assertEqual(len(valeurs), 49)
        self.assertEqual(envoyes['usehorizon'], ['1'])
        for valeur in valeurs:
            float(valeur)  # aucune valeur illisible ne part

    def test_la_liste_part_du_nord_et_tourne_dans_le_sens_horaire(self):
        profil = profil_24_directions()
        hauteurs = reechantillonner_pour_pvgis(profil)
        self.assertEqual(len(hauteurs), 24)
        self.assertEqual(hauteurs[0], hauteur_a(profil, 0.0))     # nord
        self.assertEqual(hauteurs[6], hauteur_a(profil, 90.0))    # est
        self.assertEqual(hauteurs[12], hauteur_a(profil, 180.0))  # sud
        self.assertEqual(hauteurs[18], hauteur_a(profil, 270.0))  # ouest
        # Est et ouest DIFFÈRENT sur ce site : un sens inversé casserait le
        # test au lieu de passer par hasard.
        self.assertNotEqual(hauteur_a(profil, 90.0),
                            hauteur_a(profil, 270.0))

    def test_la_hauteur_au_sud_est_conservee_exactement_sur_24_directions(
            self):
        profil = profil_24_directions()
        hauteurs = reechantillonner_pour_pvgis(profil)
        self.assertEqual(hauteurs[12], hauteur_a(profil, 180.0))

    def test_la_hauteur_au_sud_survit_au_reechantillonnage_du_profil_reel(
            self):
        profil = profil_reel()
        hauteurs = reechantillonner_pour_pvgis(profil)
        pas = 360.0 / len(hauteurs)
        rang = 180.0 / pas
        bas, haut = int(rang), int(rang) + 1
        part = rang - bas
        relu = hauteurs[bas] + part * (hauteurs[haut] - hauteurs[bas])
        self.assertLess(abs(relu - hauteur_a(profil, 180.0)),
                        TOLERANCE_SUD_DEG,
                        'hauteur au sud après rééchantillonnage : %.3f° '
                        'contre %.3f° relevés' % (relu,
                                                  hauteur_a(profil, 180.0)))


class TroisCasExclusifs(SimpleTestCase):
    """Chaque cas est PUBLIÉ, et deux masques ne s'appliquent jamais."""

    def test_un_profil_transmis_fait_foi_et_le_bloc_le_dit(self):
        profil = profil_reel()
        resultat, envoyes = appeler(horizon=profil)
        self.assertIn('userhorizon', envoyes)
        self.assertEqual(resultat['meteo']['horizon'], {
            'origine': 'profil_mesure',
            'hauteur_max_deg': profil['hauteur_max_deg'],
            'base_horizon': profil['base_horizon'],
        })

    def test_un_profil_saisi_est_publie_comme_saisie(self):
        releve = profil_saisi(profil_24_directions()['points'],
                              note='relevé de test')
        resultat, envoyes = appeler(horizon=releve)
        self.assertIn('userhorizon', envoyes)
        self.assertEqual(resultat['meteo']['horizon']['origine'], 'saisie')
        self.assertIsNone(resultat['meteo']['horizon']['base_horizon'])

    def test_sans_profil_cest_le_modele_de_terrain_de_pvgis(self):
        resultat, envoyes = appeler()
        self.assertNotIn('userhorizon', envoyes)
        self.assertEqual(envoyes['usehorizon'], ['1'])
        self.assertEqual(resultat['meteo']['horizon'], {
            'origine': 'dem_pvgis', 'hauteur_max_deg': None,
            'base_horizon': 'DEM-calculated'})

    def test_un_masque_deja_dans_la_geometrie_coupe_lhorizon_de_pvgis(self):
        resultat, envoyes = appeler(masque_dans_la_geometrie=True)
        self.assertEqual(envoyes['usehorizon'], ['0'])
        self.assertNotIn('userhorizon', envoyes)
        self.assertEqual(resultat['meteo']['horizon'], {
            'origine': 'aucun', 'hauteur_max_deg': None,
            'base_horizon': None})

    def test_profil_et_geometrie_ensemble_sont_refuses(self):
        with self.assertRaises(EntreeInvalide) as leve:
            appeler(horizon=profil_reel(), masque_dans_la_geometrie=True)
        self.assertEqual(leve.exception.champ, 'horizon')
        self.assertIn('EXCLUSIFS', leve.exception.args[0])

    def test_un_profil_sans_provenance_nest_pas_envoye(self):
        anonyme = dict(profil_reel())
        anonyme.pop('source')
        with self.assertRaises(EntreeInvalide) as leve:
            appeler(horizon=anonyme)
        self.assertEqual(leve.exception.champ, 'horizon')


class ProfilRefuse(SimpleTestCase):
    """Un masque troué ou trop court ne part pas — et on dit où ça manque."""

    def test_un_profil_qui_ne_fait_pas_le_tour_nomme_lazimut_manquant(self):
        profil = profil_reel()
        trous = (97.5, 105.0, 112.5, 120.0, 127.5)
        perce = dict(profil, points=[
            point for point in profil['points']
            if round(point['azimut_face_deg'] % 360.0, 3) not in trous])
        self.assertEqual(len(perce['points']), len(profil['points']) - 5)
        with self.assertRaises(EntreeInvalide) as leve:
            reechantillonner_pour_pvgis(perce)
        motif = leve.exception.args[0]
        self.assertEqual(leve.exception.champ, 'horizon')
        self.assertIn('90.0', motif)
        self.assertIn('135.0', motif)
        self.assertIn('112.5', motif)  # l'azimut manquant, au milieu du trou

    def test_un_profil_trop_court_est_refuse(self):
        court = dict(profil_reel(), points=profil_reel()['points'][:4])
        with self.assertRaises(EntreeInvalide) as leve:
            reechantillonner_pour_pvgis(court)
        self.assertEqual(leve.exception.champ, 'horizon')

    def test_un_profil_vide_est_refuse(self):
        with self.assertRaises(EntreeInvalide):
            reechantillonner_pour_pvgis({'points': []})

    def test_un_point_illisible_nomme_son_rang(self):
        profil = profil_reel()
        casse = dict(profil, points=[dict(point) for point in
                                     profil['points']])
        casse['points'][3]['hauteur_deg'] = 'haut'
        with self.assertRaises(EntreeInvalide) as leve:
            reechantillonner_pour_pvgis(casse)
        self.assertEqual(leve.exception.champ, 'horizon[3]')
