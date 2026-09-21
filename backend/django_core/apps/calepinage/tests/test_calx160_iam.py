# -*- coding: utf-8 -*-
"""CALX160 — l'IAM est de la physique citée, jamais un coefficient maison.

CE QUI EST PROUVÉ ICI
---------------------
1. **Propriété du modèle** : ``IAM(0°) = 1,0`` exactement, décroissance
   MONOTONE jusqu'à 85°, et ``IAM_fresnel(60°)`` dans la plage publiée par
   la page PVsyst citée (0,90 à 0,97 ; valeur calculée : 0,9476).
2. **Aucun coefficient inventé** : ``ashrae`` demandé sans ``b0`` saisi
   RETOMBE sur ``fresnel`` et le DIT dans ``entree.modele`` /
   ``entree.repli``. Idem pour ``martin_ruiz``, dont le ``a_r`` ne figure
   pas au registre de CALX145.
3. **Le diffus n'est pas du direct** : il reçoit l'IAM du modèle à l'angle
   d'incidence EFFECTIF de Brandemuehl & Beckman, et le réfléchi le sien —
   trois traitements distincts, trois valeurs distinctes.

ÉCART ASSUMÉ AU TEXTE DE LA TÂCHE (mesuré, pas supposé)
---------------------------------------------------------
Le plan attend que la perte annuelle soit « strictement INFÉRIEURE à la
perte du modèle appliqué à TOUTE l'irradiance ». Sur la fixture réelle
(Casablanca, pan à 15°) c'est l'inverse qui est vrai, et pour une raison
physique : le réfléchi du sol arrive sous un angle RASANT (θ_eff = 81,9°,
IAM = 0,560) quand le direct arrive en moyenne à 37,5° (IAM ≈ 0,996).
Traiter tout comme du direct SOUS-estime donc la perte —
2,9988 % contre 3,1227 % réellement (mesuré le 21/09/2026 sur cette
fixture). Ce fichier prouve donc la propriété que la tâche VISE — le diffus
et le réfléchi ne sont pas traités comme du direct — au lieu d'une
inégalité dont le sens dépend de l'inclinaison.

Aucune base de données, aucun réseau : ``SimpleTestCase`` et la réponse
PVGIS v5_3 RÉELLE enregistrée le 21/09/2026.

Run :
    python manage.py test apps.calepinage.tests.test_calx160_iam
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import LIBELLES, appliquer_chaine
from apps.calepinage.services.etapes import iam as etape_iam
from apps.calepinage.services.pvgis_serie import (
    MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache)
from core.calepinage.soleil import position_solaire

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
AVEC_COMPOSANTES = 'seriescalc_casablanca_sud_composantes.json'
SANS_COMPOSANTES = 'seriescalc_casablanca_sud_irradiance.json'

SITE = {'lat': 33.5, 'lon': -7.6, 'altitude_m': 139.0}
PLAN = {'cle': 'PAN-SUD', 'inclinaison_deg': 15.0, 'azimut_pvgis_deg': 0.0}
METEO_UTC = {'heure': {'base': 'utc', 'fuseau_site': 'UTC',
                       'decalage_minutes': 0}}

#: La plage publiée par la page PVsyst citée pour l'IAM de Fresnel à 60°.
PLAGE_SOIXANTE = (0.90, 0.97)


class TransportEnregistre:
    def __init__(self, charge):
        self.charge = charge

    def __call__(self, url, timeout_s):
        return 200, json.dumps(self.charge)


def serie_de(fixture, *, composantes):
    charge = json.loads((FIXTURES / fixture).read_text(encoding='utf-8'))
    client = ClientPvgis(TransportEnregistre(charge), cache=_Cache(),
                         dormir=lambda _s: None)
    resultat = client.serie_irradiance(
        lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
        annee_debut=2020, annee_fin=2020, composantes=composantes,
        obtenue_le='2026-09-21T09:00:00Z')
    return resultat['serie_horaire']


def contexte_de(**extra):
    contexte = {'site': dict(SITE), 'plans': [dict(PLAN)],
                'meteo': json.loads(json.dumps(METEO_UTC))}
    contexte.update(extra)
    return contexte


def somme(serie, colonne):
    return sum(point[colonne] or 0.0 for point in serie['points'])


class ModeleTest(SimpleTestCase):
    """Le modèle lui-même : des propriétés, pas des valeurs attendues."""

    def test_l_incidence_normale_ne_coute_rien(self):
        self.assertEqual(etape_iam._iam_fresnel(0.0), 1.0)

    def test_la_decroissance_est_monotone_jusqu_a_quatre_vingt_cinq(self):
        valeurs = [etape_iam._iam_fresnel(dixiemes / 10.0)
                   for dixiemes in range(0, 851)]
        for rang in range(len(valeurs) - 1):
            self.assertGreaterEqual(valeurs[rang], valeurs[rang + 1],
                                    f'{rang / 10.0}°')
        self.assertLess(valeurs[-1], valeurs[0])

    def test_a_soixante_degres_la_valeur_est_dans_la_plage_publiee(self):
        valeur = etape_iam._iam_fresnel(60.0)
        self.assertGreater(valeur, PLAGE_SOIXANTE[0])
        self.assertLess(valeur, PLAGE_SOIXANTE[1])

    def test_derriere_le_plan_il_n_y_a_plus_de_direct(self):
        self.assertEqual(etape_iam._iam_fresnel(90.0), 0.0)
        self.assertEqual(etape_iam._iam_fresnel(130.0), 0.0)

    def test_un_verre_antireflet_transmet_mieux(self):
        for angle in (0.0, 30.0, 60.0):
            nu = etape_iam._iam_fresnel(angle)
            traite = etape_iam._iam_fresnel(
                angle, etape_iam.INDICE_VERRE_ANTIREFLET)
            self.assertGreaterEqual(traite, nu, f'{angle}°')

    def test_l_ashrae_est_le_sien_et_reste_borne(self):
        self.assertEqual(etape_iam._iam_ashrae(0.0, 0.05), 1.0)
        self.assertLess(etape_iam._iam_ashrae(60.0, 0.05), 1.0)
        self.assertEqual(etape_iam._iam_ashrae(89.9, 5.0), 0.0)

    def test_les_angles_effectifs_sont_ceux_de_la_formule_citee(self):
        ciel, sol = etape_iam._angles_effectifs(15.0)
        self.assertAlmostEqual(ciel, 59.7 - 0.1388 * 15 + 0.001497 * 225,
                               places=9)
        self.assertAlmostEqual(sol, 90.0 - 0.5788 * 15 + 0.002693 * 225,
                               places=9)


class SurLaFixtureTest(SimpleTestCase):
    """Sur une réponse PVGIS réelle : une perte positive, et découpée."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _perte_pct(self, serie, rendue):
        avant = somme(serie, 'gi_w_m2')
        return 100.0 * (1.0 - somme(rendue, 'gi_w_m2') / avant)

    def test_la_perte_annuelle_est_strictement_positive_et_plausible(self):
        rendue, etape = etape_iam.appliquer(self.serie, contexte_de())
        self.assertEqual(etape['motif_omission'], '')
        perte = self._perte_pct(self.serie, rendue)
        self.assertGreater(perte, 0.0)
        self.assertLess(perte, 10.0,
                        'une perte d’incidence à deux chiffres sur un pan '
                        'plein sud à 15° serait un signe d’erreur.')

    def test_le_diffus_et_le_reflechi_ne_sont_pas_traites_comme_du_direct(
            self):
        rendue, etape = etape_iam.appliquer(self.serie, contexte_de())
        mixte = self._perte_pct(self.serie, rendue)

        # Le même modèle, mais appliqué à TOUTE l'irradiance sous l'angle du
        # DIRECT — exactement ce que le découpage de CALX152 existe pour
        # éviter.
        reste = 0.0
        for point in self.serie['points']:
            position = position_solaire(
                SITE['lat'], SITE['lon'], annee=point['annee'],
                mois=point['mois'], jour=point['jour'],
                heure_utc=point['heure'])
            angle = position.angle_incidence_deg(
                PLAN['inclinaison_deg'], PLAN['azimut_pvgis_deg'])
            reste += (point['gi_w_m2'] or 0.0) * etape_iam._iam_fresnel(angle)
        tout_direct = 100.0 * (1.0 - reste / somme(self.serie, 'gi_w_m2'))

        self.assertNotAlmostEqual(
            mixte, tout_direct, places=3,
            msg='si le diffus recevait l’IAM du direct, les deux pertes '
                'seraient les mêmes.')
        self.assertLess(etape['entree']['iam_reflechi'],
                        etape['entree']['iam_diffus'],
                        'le réfléchi du sol arrive plus rasant que le diffus '
                        'du ciel sur un pan à 15°.')
        self.assertLess(etape['entree']['iam_diffus'], 1.0)

    def test_les_trois_composantes_reculent_chacune_a_son_rythme(self):
        rendue, etape = etape_iam.appliquer(self.serie, contexte_de())
        rapports = {}
        for colonne in ('gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2'):
            rapports[colonne] = somme(rendue, colonne) / somme(self.serie,
                                                               colonne)
        self.assertAlmostEqual(rapports['gd_i_w_m2'],
                               etape['entree']['iam_diffus'], places=6)
        self.assertAlmostEqual(rapports['gr_i_w_m2'],
                               etape['entree']['iam_reflechi'], places=6)
        self.assertGreater(rapports['gb_i_w_m2'], rapports['gd_i_w_m2'])

    def test_un_verre_antireflet_coute_moins_cher(self):
        nu, _etape = etape_iam.appliquer(self.serie, contexte_de())
        traite, etape = etape_iam.appliquer(
            self.serie, contexte_de(fiche_module={'revetement_ar': True}))
        self.assertTrue(etape['entree']['revetement_ar'])
        self.assertEqual(etape['entree']['indice_verre'],
                         etape_iam.INDICE_VERRE_ANTIREFLET)
        self.assertLess(self._perte_pct(self.serie, traite),
                        self._perte_pct(self.serie, nu))

    def test_la_serie_d_entree_n_est_jamais_modifiee(self):
        empreinte = json.dumps(self.serie, sort_keys=True)
        etape_iam.appliquer(self.serie, contexte_de())
        self.assertEqual(json.dumps(self.serie, sort_keys=True), empreinte,
                         'une étape est PURE : elle copie, elle ne mute pas.')

    def test_le_libelle_est_celui_que_l_ordre_declare(self):
        _rendue, etape = etape_iam.appliquer(self.serie, contexte_de())
        self.assertEqual(etape['libelle'], LIBELLES['iam'])


class ChoixDuModeleTest(SimpleTestCase):
    """Aucun coefficient société n'est jamais supposé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _entree(self, reglages):
        _rendue, etape = etape_iam.appliquer(
            self.serie, contexte_de(reglages_simulation=reglages))
        self.assertEqual(etape['motif_omission'], '')
        return etape

    def test_par_defaut_c_est_fresnel_et_sa_source_est_le_texte(self):
        etape = self._entree({})
        self.assertEqual(etape['entree']['modele'], 'fresnel')
        self.assertEqual(etape['entree']['indice_verre'],
                         etape_iam.INDICE_VERRE)
        self.assertEqual(etape['source'], 'texte')
        self.assertIn('Fresnel', etape['reference'])
        self.assertIn('1,526', etape['reference'])
        self.assertNotIn('modele_demande', etape['entree'])

    def test_ashrae_sans_b0_retombe_sur_fresnel_en_le_disant(self):
        etape = self._entree({'modele_iam': {'valeur': 'ashrae',
                                             'source': 'societe'}})
        self.assertEqual(etape['entree']['modele'], 'fresnel')
        self.assertEqual(etape['entree']['modele_demande'], 'ashrae')
        self.assertIn('b0_iam', etape['entree']['repli'])
        self.assertIn('aucun b0 par défaut', etape['entree']['repli'])

    def test_ashrae_avec_un_b0_source_s_applique(self):
        etape = self._entree({
            'modele_iam': {'valeur': 'ashrae', 'source': 'societe'},
            'b0_iam': {'valeur': 0.05, 'source': 'texte',
                       'reference': 'ASHRAE 93-77'}})
        self.assertEqual(etape['entree']['modele'], 'ashrae')
        self.assertEqual(etape['entree']['b0'], 0.05)
        self.assertEqual(etape['source'], 'texte')
        ciel, _sol = etape_iam._angles_effectifs(PLAN['inclinaison_deg'])
        self.assertAlmostEqual(etape['entree']['iam_diffus'],
                               etape_iam._iam_ashrae(ciel, 0.05), places=5)

    def test_un_b0_sans_source_ne_s_applique_pas(self):
        etape = self._entree({
            'modele_iam': {'valeur': 'ashrae', 'source': 'societe'},
            'b0_iam': {'valeur': 0.05}})
        self.assertEqual(etape['entree']['modele'], 'fresnel')
        self.assertIn('b0_iam', etape['entree']['repli'])

    def test_martin_ruiz_nomme_la_cle_absente_du_registre(self):
        etape = self._entree({'modele_iam': {'valeur': 'martin_ruiz',
                                             'source': 'societe'}})
        self.assertEqual(etape['entree']['modele'], 'fresnel')
        self.assertIn('a_r', etape['entree']['repli'])
        self.assertIn('CALX145', etape['entree']['repli'])

    def test_un_modele_inconnu_retombe_sur_fresnel_en_le_nommant(self):
        etape = self._entree({'modele_iam': {'valeur': 'maison',
                                             'source': 'societe'}})
        self.assertEqual(etape['entree']['modele'], 'fresnel')
        self.assertIn('maison', etape['entree']['repli'])


class EntreeManquanteTest(SimpleTestCase):
    """Chaque absence est NOMMÉE — jamais un angle supposé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def _omise(self, contexte):
        rendue, etape = etape_iam.appliquer(self.serie, contexte)
        self.assertIs(rendue, self.serie)
        self.assertTrue(etape['motif_omission'])
        self.assertIsNone(etape['source'])
        return etape['motif_omission']

    def test_sans_composantes_le_motif_est_celui_de_calx152(self):
        serie = serie_de(SANS_COMPOSANTES, composantes=False)
        _rendue, etape = etape_iam.appliquer(serie, contexte_de())
        self.assertEqual(etape['motif_omission'], MOTIF_COMPOSANTES_ABSENTES)

    def test_sans_inclinaison_le_champ_est_nomme(self):
        contexte = contexte_de()
        contexte['plans'] = [{'cle': 'P1', 'azimut_pvgis_deg': 0.0}]
        self.assertIn('plan.inclinaison_deg', self._omise(contexte))

    def test_sans_azimut_le_champ_est_nomme(self):
        contexte = contexte_de()
        contexte['plans'] = [{'cle': 'P1', 'inclinaison_deg': 15.0}]
        self.assertIn('plan.azimut_pvgis_deg', self._omise(contexte))

    def test_plusieurs_pans_sans_designation_ne_sont_pas_arbitres(self):
        contexte = contexte_de()
        contexte['plans'] = [dict(PLAN),
                             dict(PLAN, cle='PAN-EST',
                                  azimut_pvgis_deg=-90.0)]
        motif = self._omise(contexte)
        self.assertIn('2 pans', motif)
        self.assertIn('ne choisit pas', motif)

    def test_un_pan_designe_est_retrouve_dans_la_liste(self):
        contexte = contexte_de(plan='PAN-EST')
        contexte['plans'] = [dict(PLAN),
                             dict(PLAN, cle='PAN-EST',
                                  azimut_pvgis_deg=-90.0)]
        _rendue, etape = etape_iam.appliquer(self.serie, contexte)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['azimut_pvgis_deg'], -90.0)

    def test_sans_coordonnees_le_site_est_nomme(self):
        contexte = contexte_de()
        contexte['site'] = {'lon': -7.6}
        self.assertIn('site.lat', self._omise(contexte))

    def test_sans_base_de_temps_le_champ_est_nomme(self):
        contexte = contexte_de()
        contexte['meteo'] = {'heure': {'base': 'locale_standard',
                                       'decalage_minutes': []}}
        self.assertIn('meteo.heure.decalage_minutes', self._omise(contexte))


class DansLaChaineTest(SimpleTestCase):
    """Vue par l'ordonnanceur : le contrat cascade tient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serie = serie_de(AVEC_COMPOSANTES, composantes=True)

    def test_l_etape_appliquee_porte_les_douze_champs(self):
        _rendue, cascade = appliquer_chaine(self.serie, contexte_de())
        etape = next(e for e in cascade['etapes'] if e['etape'] == 'iam')
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['libelle'], LIBELLES['iam'])
        self.assertEqual(etape['source'], 'texte')
        self.assertFalse(etape['gain'])
        self.assertEqual(etape['entree']['modele'], 'fresnel')

    def test_la_puissance_suit_l_irradiance_heure_par_heure(self):
        serie = {
            'pas_minutes': 60,
            'points': [
                {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
                 'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
                 'gi_w_m2': 1000.0, 'p_w': 1000.0},
            ],
        }
        rendue, etape = etape_iam.appliquer(serie, contexte_de())
        self.assertEqual(etape['motif_omission'], '')
        point = rendue['points'][0]
        self.assertAlmostEqual(point['p_w'] / 1000.0,
                               point['gi_w_m2'] / 1000.0, places=9)
        self.assertLess(point['p_w'], 1000.0)
