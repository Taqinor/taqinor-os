# -*- coding: utf-8 -*-
"""CALX182 — la simulation MODULE PAR MODULE, et son agrégation.

CE QUI EST PROUVÉ ICI
---------------------
1. **Propriété** : la somme des ``par_module[].p50_kwh`` égale
   ``total.p50_kwh`` à 0,1 kWh près.
2. **Propriété** : un layout de N modules tous à accès 1,0 rend EXACTEMENT
   la même énergie totale que la simulation par pan sur la même fixture —
   simuler module par module ne change pas le total, il le DÉTAILLE.
3. **Le plafond** : au-delà, ``par_module`` est omis AVEC son motif, et
   l'agrégat reste juste. Le plafond se saisit ; à défaut c'est celui que la
   décision fondateur a arrêté, publié avec sa provenance.
4. **Une requête météo par PLAN, jamais par module** : le fournisseur est
   appelé une fois par pan, quel que soit le nombre de modules.
5. **Les modules identiques d'un pan sont calculés une fois** et comptés
   autant de fois qu'ils sont : l'agrégat est exact, jamais échantillonné.
6. **La série agrégée** est cohérente avec le total, heure par heure.
7. **Pureté** : le contexte reçu ne bouge pas — chaque passage tourne sur sa
   copie de travail, parce que ``appliquer_chaine`` écrit dans le contexte
   qu'elle reçoit (CALX59/153/155) — et deux passages rendent le même
   document.
8. **Rien n'est supposé** : sans pan ou sans accès météo, le bloc est publié
   VIDE avec son motif — jamais un 0 kWh.

Aucune base de données, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx182_module_par_module
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services import chaine_pertes, etapes, simulation_modules
from apps.calepinage.services.chaine_pertes import appliquer_chaine

#: La méthode d'accès solaire que le document déclare (CALX158).
METHODE = {'horizon': False, 'rangees': False,
           'nom': 'shadingEngine roofPro11'}

#: Deux heures ensoleillées, composantes séparées et colonne de puissance :
#: le minimum pour qu'une énergie se lise à la sortie de la chaîne.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_w',
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0, 'p_w': 4000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
         'gb_i_w_m2': 400.0, 'gd_i_w_m2': 100.0, 'gr_i_w_m2': 0.0,
         'gi_w_m2': 500.0, 'p_w': 2000.0},
    ],
}


class Fournisseur:
    """Un fournisseur de séries qui COMPTE ses appels — aucun réseau."""

    def __init__(self, serie=None):
        self.serie = serie or SERIE
        self.appels = []

    def __call__(self, plan):
        self.appels.append(plan.get('cle') if isinstance(plan, dict)
                           else plan)
        return self.serie


def plan_de(cle, modules):
    return {'cle': cle, 'modules': modules,
            'inclinaison_deg': 15.0, 'azimut_pvgis_deg': 0.0}


def zone_de(cle, acces):
    return {'label': cle, 'geometry': {
        'solarAccess': {'values': list(acces), 'method': dict(METHODE)}}}


def affectation_de(cle, nombre, *, chaine=1, premier=1):
    return [{'module': '%s#%d' % (cle, rang), 'pan': cle, 'chaine': chaine,
             'onduleur': 1, 'mppt': 1, 'source': 'automatique'}
            for rang in range(premier, premier + nombre)]


def contexte_de(pans, *, fournisseur=None, affectation=None, **extra):
    """``pans`` : ``[(repère, [accès par module])]``."""
    fournisseur = fournisseur or Fournisseur()
    contexte = {
        'plans': [plan_de(cle, len(acces)) for cle, acces in pans],
        'site': {'lat': 33.5, 'lon': -7.6},
        'meteo': {'service': 'seriescalc',
                  'base_rayonnement': 'PVGIS-SARAH3'},
        'ombrage': {
            'solar_access': {'method': dict(METHODE)},
            'layout': {'zones': [zone_de(cle, acces) for cle, acces in pans]},
        },
        'obtenir_serie': fournisseur,
    }
    if affectation is not None:
        contexte['affectation'] = affectation
    contexte.update(extra)
    return contexte


class ProprietesDAgregation(SimpleTestCase):
    """Les trois propriétés que la tâche exige, chiffre par chiffre."""

    def test_la_somme_des_modules_est_le_total(self):
        acces = [1.0] * 9 + [0.2]
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', acces)]))
        self.assertEqual(bloc['motif'], '')
        self.assertEqual(len(bloc['par_module']), 10)
        somme = sum(ligne['p50_kwh'] for ligne in bloc['par_module'])
        self.assertAlmostEqual(somme, bloc['total']['p50_kwh'], delta=0.1)

    def test_tous_a_un_rend_le_total_de_la_simulation_par_pan(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 8)]))
        # La MÊME fixture, la MÊME chaîne, mais en une seule passe de pan —
        # sur un contexte NEUF, puisque la chaîne écrit dans celui qu'elle
        # reçoit (CALX59/155).
        sortie, _cascade = appliquer_chaine(
            SERIE, contexte_de([('PAN-A', [1.0] * 8)]))
        self.assertAlmostEqual(bloc['total']['p50_kwh'],
                               etapes.energie_kwh(sortie), places=6)

    def test_un_module_ombre_produit_moins_que_ses_voisins(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 9 + [0.2])]))
        lignes = {ligne['module']: ligne for ligne in bloc['par_module']}
        self.assertEqual(lignes['PAN-A#10']['acces_solaire_pct'], 20.0)
        self.assertLess(lignes['PAN-A#10']['p50_kwh'],
                        lignes['PAN-A#1']['p50_kwh'])

    def test_la_serie_agregee_colle_au_total(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 4 + [0.5] * 2)]))
        agregee = bloc['serie_agregee']
        self.assertIsNotNone(agregee)
        self.assertEqual(bloc['entree']['motif_serie_agregee'], '')
        self.assertAlmostEqual(etapes.energie_kwh(agregee),
                               bloc['total']['p50_kwh'], delta=0.1)
        self.assertEqual(len(agregee['points']), len(SERIE['points']))


class UneRequeteParPlan(SimpleTestCase):
    """CALX155 — une requête météo par PLAN, jamais par module."""

    def test_un_seul_appel_pour_tous_les_modules_dun_pan(self):
        fournisseur = Fournisseur()
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 12)], fournisseur=fournisseur))
        self.assertEqual(len(fournisseur.appels), 1)
        self.assertEqual(bloc['entree']['series_demandees'], 1)
        self.assertEqual(bloc['entree']['modules_simules'], 12)

    def test_deux_pans_font_deux_appels(self):
        fournisseur = Fournisseur()
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 1.0]), ('PAN-B', [0.6, 0.6])],
                        fournisseur=fournisseur))
        self.assertEqual(fournisseur.appels, ['PAN-A', 'PAN-B'])
        self.assertEqual(bloc['entree']['series_demandees'], 2)
        self.assertEqual(bloc['entree']['pans'], ['PAN-A', 'PAN-B'])
        self.assertEqual(len(bloc['par_module']), 4)

    def test_les_modules_identiques_ne_sont_calcules_quune_fois(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 9 + [0.2])]))
        # Deux valeurs d'accès distinctes ⇒ deux passages de chaîne, pour
        # dix modules publiés.
        self.assertEqual(bloc['entree']['chaines_executees'], 2)
        self.assertEqual(bloc['entree']['modules_simules'], 10)


class LePlafond(SimpleTestCase):
    """Au-delà du plafond, la liste est omise — et l'agrégat reste juste."""

    def test_plafond_saisi_tronque_la_liste_et_le_dit(self):
        reglages = {simulation_modules.CLE_PLAFOND: {
            'valeur': 3, 'source': 'societe', 'reference': 'Essai'}}
        contexte = contexte_de([('PAN-A', [1.0] * 9 + [0.2])],
                               reglages_simulation=reglages)
        bloc = simulation_modules.production_module_par_module(contexte)
        self.assertEqual(bloc['par_module'], [])
        self.assertTrue(bloc['entree']['par_module_tronque'])
        self.assertIn('3', bloc['entree']['motif_troncature'])
        self.assertIn(simulation_modules.CLE_PLAFOND,
                      bloc['entree']['motif_troncature'])
        self.assertEqual(bloc['entree']['plafond']['valeur'], 3)
        self.assertEqual(bloc['entree']['plafond']['source'],
                         simulation_modules.SOURCE_PLAFOND_SAISI)
        # L'agrégat, lui, n'est pas tronqué.
        self.assertEqual(bloc['total']['modules'], 10)
        sans_plafond = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0] * 9 + [0.2])]))
        self.assertAlmostEqual(bloc['total']['p50_kwh'],
                               sans_plafond['total']['p50_kwh'], places=6)

    def test_plafond_par_defaut_est_la_decision_citee(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 1.0])]))
        plafond = bloc['entree']['plafond']
        self.assertEqual(plafond['valeur'],
                         simulation_modules.PLAFOND_DECIDE)
        self.assertEqual(plafond['source'],
                         simulation_modules.SOURCE_PLAFOND_DECIDE)
        self.assertIn('CALX389', plafond['reference'])
        self.assertFalse(bloc['entree']['par_module_tronque'])


class AgregationParChaine(SimpleTestCase):
    """La partition RÉELLE, jamais une partition recalculée ici."""

    def test_deux_chaines_publient_leurs_totaux(self):
        acces = [1.0] * 3 + [0.4] * 3
        affectation = (affectation_de('PAN-A', 3, chaine=1)
                       + affectation_de('PAN-A', 3, chaine=2, premier=4))
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', acces)], affectation=affectation,
                        fiche_module={'pmax_w': 550.0}))
        self.assertEqual(len(bloc['par_chaine']), 2)
        une, deux = bloc['par_chaine']
        self.assertEqual((une['chaine'], deux['chaine']), (1, 2))
        self.assertEqual(une['modules'], 3)
        self.assertEqual(une['acces_solaire_min_pct'], 100.0)
        self.assertEqual(deux['acces_solaire_min_pct'], 40.0)
        self.assertEqual(une['ecart_intra_chaine_pct'], 0.0)
        self.assertGreater(une['p50_kwh'], deux['p50_kwh'])
        # Les kWc viennent de la FICHE, jamais d'une puissance supposée.
        self.assertAlmostEqual(une['kwc'], 1.65, places=3)
        self.assertAlmostEqual(bloc['total']['kwc'], 3.3, places=3)
        self.assertAlmostEqual(
            une['p50_kwh'] + deux['p50_kwh'], bloc['total']['p50_kwh'],
            delta=0.1)

    def test_sans_fiche_les_kwc_restent_inconnus(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 1.0])]))
        self.assertIsNone(bloc['total']['kwc'])

    def test_sans_affectation_aucune_chaine_nest_inventee(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 0.5])]))
        self.assertEqual(bloc['par_chaine'], [])
        self.assertTrue(all(ligne['chaine'] is None
                            for ligne in bloc['par_module']))


class RienNestSuppose(SimpleTestCase):
    """Sans entrée, un bloc VIDE et nommé — jamais un 0 kWh."""

    def test_sans_pan(self):
        bloc = simulation_modules.production_module_par_module(
            {'plans': [], 'obtenir_serie': Fournisseur()})
        self.assertEqual(bloc['motif'], simulation_modules.MOTIF_SANS_PLAN)
        self.assertIsNone(bloc['total']['p50_kwh'])
        self.assertEqual(bloc['par_module'], [])

    def test_sans_acces_meteo(self):
        contexte = contexte_de([('PAN-A', [1.0])])
        contexte.pop('obtenir_serie')
        bloc = simulation_modules.production_module_par_module(contexte)
        self.assertEqual(bloc['motif'], simulation_modules.MOTIF_SANS_METEO)
        self.assertIsNone(bloc['total']['p50_kwh'])

    def test_un_pan_sans_module_est_nomme(self):
        contexte = contexte_de([('PAN-A', [1.0, 1.0])])
        contexte['plans'].append({'cle': 'PAN-VIDE',
                                  'inclinaison_deg': 15.0,
                                  'azimut_pvgis_deg': 0.0})
        bloc = simulation_modules.production_module_par_module(contexte)
        self.assertEqual(bloc['entree']['pans_sans_module'], ['PAN-VIDE'])
        self.assertEqual(bloc['total']['modules'], 2)

    def test_une_energie_illisible_reste_inconnue(self):
        """Une série sans colonne de puissance ne produit pas « zéro »."""
        sans_puissance = {
            'pas_minutes': 60,
            'points': [{'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
                        'gi_w_m2': 1000.0}],
        }
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 1.0])],
                        fournisseur=Fournisseur(sans_puissance)))
        self.assertIsNone(bloc['total']['p50_kwh'])
        self.assertEqual(bloc['entree']['modules_sans_energie'], 2)
        self.assertIn('2', bloc['entree']['motif_energie'])

    def test_un_module_sans_acces_calcule_est_publie_sans_acces(self):
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, None])]))
        lignes = {ligne['module']: ligne for ligne in bloc['par_module']}
        self.assertIsNone(lignes['PAN-A#2']['acces_solaire_pct'])
        self.assertEqual(bloc['entree']['modules_sans_acces'], ['PAN-A#2'])


class PureteEtDeterminisme(SimpleTestCase):
    """Le contexte ne bouge pas, et deux passages rendent le même document.

    ``appliquer_chaine`` ÉCRIT dans le contexte qu'elle reçoit — accès météo
    partagé, ``meteo.appels_pvgis``, ``meteo.heure`` après le recalage
    horaire, verdict ``croisement_horaire`` (CALX59/153/155). Ce pilote ne
    lui donne donc que des COPIES DE TRAVAIL, et ces tests le prouvent des
    deux côtés : rien ne fuit vers l'appelant, et la chaîne a bien écrit.
    """

    def test_le_contexte_recu_nest_pas_modifie(self):
        contexte = contexte_de([('PAN-A', [1.0, 0.5])])
        avant = copy.deepcopy({cle: valeur for cle, valeur
                               in contexte.items()
                               if cle != 'obtenir_serie'})
        simulation_modules.production_module_par_module(contexte)
        apres = {cle: valeur for cle, valeur in contexte.items()
                 if cle != 'obtenir_serie'}
        self.assertEqual(avant, apres)
        self.assertNotIn('plan', contexte)
        self.assertNotIn(chaine_pertes.CLE_METEO_PARTAGEE, contexte)
        self.assertNotIn(chaine_pertes.CLE_CROISEMENT_HORAIRE, contexte)
        self.assertNotIn('heure', contexte['meteo'])
        self.assertNotIn('appels_pvgis', contexte['meteo'])

    def test_ce_que_la_chaine_a_pose_est_republie(self):
        """La copie isole, elle n'escamote pas : le verdict ressort."""
        bloc = simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 0.5])]))
        self.assertIsNotNone(bloc['entree']['croisement_horaire'])
        self.assertIsNotNone(bloc['entree']['meteo_heure'])
        self.assertIn('possible', bloc['entree']['croisement_horaire'])

    def test_deux_passages_rendent_le_meme_document(self):
        pans = [('PAN-A', [1.0] * 3 + [0.3]), ('PAN-B', [0.8, 0.8])]
        premier = simulation_modules.production_module_par_module(
            contexte_de(pans))
        second = simulation_modules.production_module_par_module(
            contexte_de(pans))
        self.assertEqual(premier['par_module'], second['par_module'])
        self.assertEqual(premier['total'], second['total'])

    def test_la_serie_du_pan_nest_pas_modifiee(self):
        fournisseur = Fournisseur()
        simulation_modules.production_module_par_module(
            contexte_de([('PAN-A', [1.0, 0.4])], fournisseur=fournisseur))
        self.assertEqual(
            [point['p_w'] for point in fournisseur.serie['points']],
            [4000.0, 2000.0])
