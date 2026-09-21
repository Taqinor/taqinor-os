# -*- coding: utf-8 -*-
"""CALX152 — direct, diffus et réfléchi séparés : sans quoi rien n'est honnête.

L'IAM ne s'applique qu'au faisceau DIRECT sous son angle d'incidence, et une
cellule ombrée reçoit encore le DIFFUS. Sans le découpage, ni l'IAM ni
l'ombrage ne peuvent être calculés sans inventer une répartition.

CE QUI EST PROUVÉ ICI
---------------------
1. **``components=1`` est le seul drapeau qui sépare** : l'URL le porte quand
   on demande les composantes, et pas autrement.
2. **CE QUE PVGIS FAIT VRAIMENT, ET QUI N'EST PAS DOCUMENTÉ DANS LE PLAN** :
   sous ``components=1``, PVGIS ne rend PLUS la colonne ``G(i)`` — il rend
   ``Gb(i)``, ``Gd(i)`` et ``Gr(i)``. ``gi_w_m2`` est donc la SOMME des trois,
   et ce n'est pas une estimation : c'est la décomposition de PVGIS lui-même.
3. **La propriété de somme, contre du RÉEL** : sur les points communs aux deux
   fixtures (même point, mêmes paramètres, seul ``components`` change),
   ``gb + gd + gr`` s'écarte de ``G(i)`` de moins de 1 % — écart maximum
   MESURÉ le 21/09/2026 sur 142 points ensoleillés : 0,13 %.
4. **Sans composantes, RIEN n'est réparti** : les trois clés restent ``None``,
   la série reste utilisable, et ``MOTIF_COMPOSANTES_ABSENTES`` porte le motif
   que les étapes ``iam``, ``ombrage_proche``, ``acces_module`` et
   ``inter_rangees`` publieront tel quel.
5. **``h_sun_deg`` vient de PVGIS, jamais d'un calcul** : la valeur publiée est
   la colonne ``H_sun`` de la réponse, à l'identique ; ``position_solaire``
   (CALX146) sert de CONTRÔLE, jamais de remplaçant — écart maximum MESURÉ sur
   136 points au-dessus de 5° : 0,4335°.

CE QUI N'EST PAS PROUVÉ ICI (et pourquoi)
------------------------------------------
Le plan demande aussi que les quatre étapes concernées sortent OMISES avec ce
motif et ``perte_pct`` à ``null``. ``services/etapes/`` n'existe pas encore sur
cette base (CALX147/CALX148 le posent) : le motif est donc publié ICI, en un
seul exemplaire, avec le drapeau ``composantes_disponibles`` que ces étapes
liront. L'essai des quatre étapes appartient à la lane qui les écrit.

AUCUN RÉSEAU, AUCUNE BASE — ``SimpleTestCase``, réponses PVGIS v5_3 RÉELLES
enregistrées le 21/09/2026 (bloc ``_provenance`` dans chaque fixture).

Run :
    python manage.py test apps.calepinage.tests.test_calx152_composantes
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse

from django.test import SimpleTestCase

from apps.calepinage.services.pvgis_serie import (
    COLONNES_COMPOSANTES, MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache,
)
from core.calepinage.soleil import position_solaire

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

AVEC = 'seriescalc_casablanca_sud_composantes.json'
SANS = 'seriescalc_casablanca_sud_irradiance.json'

#: Seuil de la tâche : la somme des composantes doit coller à ``G(i)`` à 1 %
#: près (écart maximum mesuré : 0,13 %).
TOLERANCE_SOMME_PCT = 1.0

#: Seuil de TEST du contrôle contre ``position_solaire`` — le même que
#: CALX146, pour la même raison (arrondi horaire de PVGIS). Écart maximum
#: mesuré : 0,4335°. Aucune valeur métier n'en dépend.
TOLERANCE_POSITION_DEG = 1.5
HAUTEUR_COMPARABLE_DEG = 5.0


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    def __init__(self, charge=None):
        self.charge = charge
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return 200, json.dumps(self.charge or {})


def appeler(fixture, **extra):
    transport = TransportEnregistre(charger(fixture))
    client = ClientPvgis(transport, cache=_Cache(), dormir=lambda _s: None)
    params = dict(lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
                  annee_debut=2020, annee_fin=2020,
                  obtenue_le='2026-09-21T09:00:00Z')
    params.update(extra)
    resultat = client.serie_irradiance(**params)
    envoyes = urllib.parse.parse_qs(
        urllib.parse.urlparse(transport.appels[0]).query)
    return resultat, envoyes


class DrapeauComponents(SimpleTestCase):
    """``components=1`` part, et seulement quand on le demande."""

    def test_il_part_quand_les_composantes_sont_demandees(self):
        _resultat, envoyes = appeler(AVEC, composantes=True)
        self.assertEqual(envoyes['components'], ['1'])

    def test_il_ne_part_pas_autrement(self):
        _resultat, envoyes = appeler(SANS)
        self.assertNotIn('components', envoyes)


class AvecComposantes(SimpleTestCase):
    """La réponse à composantes est lue en entier, sans rien supposer."""

    def setUp(self):
        self.resultat, _envoyes = appeler(AVEC, composantes=True)

    def test_pvgis_ne_rend_plus_g_i_sous_components(self):
        # Le fait qui justifie la somme : il est VÉRIFIÉ sur la fixture, pas
        # supposé d'après la documentation.
        for ligne in charger(AVEC)['outputs']['hourly']:
            self.assertNotIn('G(i)', ligne)
            for colonne in ('Gb(i)', 'Gd(i)', 'Gr(i)'):
                self.assertIn(colonne, ligne)

    def test_les_trois_composantes_sont_sur_chaque_point(self):
        manquants = [point for point in self.resultat['points']
                     if any(point[colonne] is None
                            for colonne in COLONNES_COMPOSANTES)]
        self.assertEqual(manquants, [])
        self.assertTrue(self.resultat['composantes_disponibles'])
        self.assertIsNone(self.resultat['motif_composantes'])

    def test_la_globale_est_la_somme_rendue_par_pvgis(self):
        for point in self.resultat['points']:
            somme = (point['gb_i_w_m2'] + point['gd_i_w_m2']
                     + point['gr_i_w_m2'])
            self.assertAlmostEqual(point['gi_w_m2'], somme, places=9)

    def test_les_colonnes_sont_declarees_a_la_place_du_contrat(self):
        colonnes = self.resultat['serie_horaire']['colonnes']
        self.assertEqual(
            colonnes,
            ['annee', 'mois', 'jour', 'heure', 'gi_w_m2', 't2m_c',
             'gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2', 'ws10m', 'h_sun_deg'])

    def test_les_valeurs_sont_celles_de_la_reponse_enregistree(self):
        midi = [ligne for ligne in charger(AVEC)['outputs']['hourly']
                if ligne['time'] == '20200115:1209'][0]
        point = [p for p in self.resultat['points']
                 if (p['mois'], p['jour'], p['heure']) == (1, 15, 12)][0]
        self.assertEqual(point['gb_i_w_m2'], midi['Gb(i)'])
        self.assertEqual(point['gd_i_w_m2'], midi['Gd(i)'])
        self.assertEqual(point['gr_i_w_m2'], midi['Gr(i)'])


class ProprieteDeSomme(SimpleTestCase):
    """``gb + gd + gr`` contre le ``G(i)`` de la MÊME requête sans components.

    Les deux fixtures sont deux réponses RÉELLES du même point, aux mêmes
    paramètres : seul ``components`` change. C'est la comparaison la plus
    serrée possible — et la seule disponible, puisque PVGIS ne sert pas
    ``G(i)`` en même temps que ses composantes.
    """

    def test_lecart_reste_sous_un_pour_cent(self):
        par_heure = {ligne['time']: ligne
                     for ligne in charger(SANS)['outputs']['hourly']}
        pires = []
        compares = 0
        for ligne in charger(AVEC)['outputs']['hourly']:
            reference = par_heure.get(ligne['time'])
            if reference is None or reference['G(i)'] <= 0.0:
                continue
            compares += 1
            somme = ligne['Gb(i)'] + ligne['Gd(i)'] + ligne['Gr(i)']
            ecart = abs(somme - reference['G(i)']) / reference['G(i)'] * 100.0
            if ecart >= TOLERANCE_SOMME_PCT:
                pires.append((ligne['time'], round(ecart, 4)))
        self.assertEqual(pires, [],
                         'somme des composantes trop loin de G(i) : %r'
                         % (pires,))
        self.assertGreater(compares, 100)


class SansComposantes(SimpleTestCase):
    """Rien n'est réparti : les clés restent nulles et le motif le dit."""

    def setUp(self):
        self.resultat, _envoyes = appeler(SANS)

    def test_les_trois_cles_existent_et_restent_nulles(self):
        for point in self.resultat['points']:
            for colonne in COLONNES_COMPOSANTES:
                self.assertIn(colonne, point)
                self.assertIsNone(point[colonne])

    def test_la_serie_reste_utilisable(self):
        self.assertEqual(len(self.resultat['points']), 288)
        sans_globale = [point for point in self.resultat['points']
                        if point['gi_w_m2'] is None]
        self.assertEqual(sans_globale, [])

    def test_le_motif_est_publie_une_seule_fois_et_mot_pour_mot(self):
        self.assertFalse(self.resultat['composantes_disponibles'])
        self.assertEqual(self.resultat['motif_composantes'],
                         MOTIF_COMPOSANTES_ABSENTES)
        self.assertEqual(
            MOTIF_COMPOSANTES_ABSENTES,
            "les composantes directe/diffuse de l'irradiance ne sont pas "
            'disponibles pour cette réponse PVGIS : aucune part diffuse '
            "n'est supposée")

    def test_les_colonnes_ne_promettent_pas_ce_qui_nest_pas_la(self):
        for colonne in COLONNES_COMPOSANTES:
            self.assertNotIn(colonne,
                             self.resultat['serie_horaire']['colonnes'])


class HauteurDuSoleil(SimpleTestCase):
    """``h_sun_deg`` vient de PVGIS ; le noyau ne fait que CONTRÔLER."""

    def test_la_valeur_publiee_est_celle_de_la_reponse(self):
        resultat, _envoyes = appeler(AVEC, composantes=True)
        par_heure = {ligne['time']: ligne
                     for ligne in charger(AVEC)['outputs']['hourly']}
        for point in resultat['points']:
            horodatage = '%04d%02d%02d:%02d09' % (
                point['annee'], point['mois'], point['jour'], point['heure'])
            self.assertEqual(point['h_sun_deg'],
                             par_heure[horodatage]['H_sun'])

    def test_le_controle_contre_position_solaire_tient(self):
        charge = charger(AVEC)
        latitude = charge['inputs']['location']['latitude']
        longitude = charge['inputs']['location']['longitude']
        pires = []
        compares = 0
        for ligne in charge['outputs']['hourly']:
            hauteur = float(ligne['H_sun'])
            if hauteur <= HAUTEUR_COMPARABLE_DEG:
                continue
            compares += 1
            horodatage = ligne['time']
            calculee = position_solaire(
                latitude, longitude,
                annee=int(horodatage[0:4]), mois=int(horodatage[4:6]),
                jour=int(horodatage[6:8]),
                heure_utc=(int(horodatage[9:11])
                           + int(horodatage[11:13]) / 60.0)).elevation_deg
            ecart = abs(calculee - hauteur)
            if ecart >= TOLERANCE_POSITION_DEG:
                pires.append((horodatage, round(ecart, 3)))
        self.assertEqual(pires, [],
                         'H_sun trop loin de position_solaire : %r' % (pires,))
        self.assertGreater(compares, 100)
