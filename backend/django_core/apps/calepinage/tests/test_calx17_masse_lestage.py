"""CALX17 — la masse posée et la feuille de lestage, enfin servies en HTTP.

CE QUE CE FICHIER PROUVE
------------------------
``services/lestage.py`` composait la masse au m² et la feuille de lestage
depuis le poids de FICHE et les saisies de la société… sans aucun appelant
hors de ses propres tests : une capacité construite, testée, et injoignable.
CALX17 pose la porte ``GET calepinages/<pk>/masse-lestage/`` et le panneau
qui la lit. Les essais ci-dessous vérifient, SANS base de données :

1. la route EXISTE dans la table que DRF construira (``get_extra_actions()``),
   en lecture seule et gardée par ``PeutVoirCalepinage`` ;
2. l'échantillon COMMITTÉ ``contract_samples/calepinage_masse_lestage.json``
   est, au caractère près, ce que le service rend sur un calepinage NU — le
   test frontend lit LE MÊME fichier, les deux moitiés ne peuvent plus
   diverger (PACT10) ;
3. la règle « zéro chiffre inventé » tient dans les deux sens : chaque
   paramètre publié porte sa SOURCE, et un paramètre non saisi laisse la
   ligne NON calculée en NOMMANT le champ manquant ;
4. sans poids de fiche produit, AUCUNE masse n'est publiée et le champ
   fautif est nommé ;
5. un ``?module=`` non numérique est refusé en NOMMANT le champ — jamais un
   « non enregistré » générique, jamais un 500.

Essais PURS : aucune base, aucun réseau. Run ::

    python manage.py test apps.calepinage.tests.test_calx17_masse_lestage -v 2
"""
from __future__ import annotations

import importlib
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.lestage import (
    PARAMETRES,
    _feuille_de_lestage,
    masse_et_lestage,
)

ECHANTILLON = (pathlib.Path(__file__).resolve().parent.parent
               / 'contract_samples' / 'calepinage_masse_lestage.json')

#: Les clés qu'une ligne de feuille porte TOUJOURS — c'est ce que le panneau
#: affiche : la formule, ses entrées, et ce qui manque quand rien n'est servi.
CLES_DE_LIGNE = ('code', 'libelle', 'valeur', 'unite', 'formule', 'entrees',
                 'manquants', 'mention')


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode.

    L'import d'``urls`` exécute les rattachements par attribut de classe : la
    table serait autrement celle du viewset nu.
    """
    importlib.import_module('apps.calepinage.urls')
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class CalepinageNu:
    """Un calepinage NU : aucun devis, aucun document — donc aucune base."""

    pk = 1
    devis_id = None
    roof_layout = None
    resultat = None
    company = None
    layout_hash = ''
    titre = 'Calepinage 1'


class FausseRequete:
    def __init__(self, **parametres):
        self.query_params = dict(parametres)


class FauxViewSet:
    """Le strict nécessaire pour appeler l'action hors de toute requête."""

    def __init__(self, calepinage):
        self._calepinage = calepinage

    def get_object(self):
        return self._calepinage


class RouteMasseLestageTest(SimpleTestCase):
    """La porte existe, en lecture seule, gardée."""

    def test_l_action_est_enregistree(self):
        _viewset, actions = _actions()
        chemins = {methode.url_path for methode in actions.values()}
        self.assertIn(
            'masse-lestage', chemins,
            "L'URL « calepinages/<pk>/masse-lestage/ » n'est pas enregistrée "
            "(CALX17) : vérifier que le nom de la fonction, celui de "
            "l'attribut de classe et la clé du mapping DRF sont identiques.")

    def test_l_action_reste_en_lecture_seule_et_gardee(self):
        _viewset, actions = _actions()
        action = actions['masse_lestage']
        self.assertEqual(set(action.mapping), {'get'},
                         "La masse et le lestage se LISENT : cette action ne "
                         "doit rien écrire.")
        self.assertEqual(
            [garde.__name__
             for garde in action.kwargs['permission_classes']],
            ['PeutVoirCalepinage'])
        self.assertEqual(action.url_name, 'masse-lestage')


class ContratMasseLestageTest(SimpleTestCase):
    """L'échantillon committé EST ce que le service rend."""

    def test_l_exemple_vide_est_la_sortie_reelle_du_service(self):
        contrat = _contrat()
        self.assertEqual(
            masse_et_lestage(CalepinageNu()), contrat['exemple_vide'],
            "L'échantillon « exemple_vide » ne décrit plus la sortie réelle "
            "de masse_et_lestage sur un calepinage nu : le panneau qui le lit "
            "afficherait une forme que le serveur ne sert pas.")

    def test_la_reponse_ne_porte_que_les_deux_blocs_du_service(self):
        contrat = _contrat()
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(contrat[etat]), ['lestage', 'masse'],
                             f"{etat} : la vue rend la sortie du service TELLE "
                             "QUELLE — aucune clé ajoutée par la porte.")

    def test_chaque_ligne_porte_sa_formule_ses_entrees_et_ses_manquants(self):
        contrat = _contrat()
        for etat in ('exemple', 'exemple_vide'):
            for ligne in contrat[etat]['lestage']['lignes']:
                for cle in CLES_DE_LIGNE:
                    self.assertIn(cle, ligne,
                                  f"{etat}/{ligne.get('code')} : clé "
                                  f"« {cle} » absente.")
                self.assertTrue(ligne['formule'],
                                f"{etat}/{ligne['code']} : une ligne sans "
                                "formule ne peut pas être relue.")
                self.assertTrue(ligne['entrees'],
                                f"{etat}/{ligne['code']} : une ligne sans "
                                "entrées ne cite pas d'où elle vient.")

    def test_une_ligne_non_calculee_nomme_toujours_ce_qui_manque(self):
        contrat = _contrat()
        for etat in ('exemple', 'exemple_vide'):
            for ligne in contrat[etat]['lestage']['lignes']:
                if ligne['valeur'] is None:
                    self.assertTrue(
                        ligne['manquants'] and ligne['mention'],
                        f"{etat}/{ligne['code']} : ligne non calculée sans "
                        "champ manquant nommé — l'écran ne pourrait pas dire "
                        "quoi saisir.")
                else:
                    self.assertEqual(ligne['manquants'], [])

    def test_aucun_parametre_publie_sans_sa_source(self):
        contrat = _contrat()
        for parametre in contrat['exemple']['lestage']['parametres']:
            self.assertIn(parametre['cle'], PARAMETRES)
            self.assertTrue(
                str(parametre['source']).strip(),
                f"Le paramètre « {parametre['cle']} » est publié sans source : "
                "un chiffre qu'on ne peut pas sourcer ne se défend pas.")
        self.assertTrue(contrat['exemple']['lestage']['mention'])


class SansPoidsDeFicheTest(SimpleTestCase):
    """Sans poids de fiche : aucune masse, et le champ fautif est nommé."""

    def test_aucune_masse_et_le_champ_fautif_est_nomme(self):
        masse = _contrat()['exemple_vide']['masse']
        self.assertIsNone(masse['masse_totale_kg'])
        self.assertIsNone(masse['poids_unitaire']['module_kg'])
        quoi = [manquant['quoi'] for manquant in masse['manquants']]
        self.assertIn(
            'poids_module', quoi,
            "La masse n'est pas publiée mais RIEN ne dit pourquoi : le bloc "
            "doit nommer le champ fautif (« poids_kg » de la fiche).")
        for manquant in masse['manquants']:
            self.assertTrue(manquant['message'].strip())

    def test_un_coefficient_non_saisi_laisse_la_ligne_omise(self):
        """Le cas central de la règle « zéro chiffre inventé »."""
        source = 'saisie société (essai)'
        section = {cle: {'valeur': 'rase campagne' if cle == 'categorie_terrain'
                         else 1, 'source': source}
                   for cle in PARAMETRES if cle != 'coefficient_frottement'}
        feuille = _feuille_de_lestage(section, surface_module_m2=2.0,
                                      masse_module_kg=22.0, societe='Essai')
        lignes = {ligne['code']: ligne for ligne in feuille['lignes']}
        glissement = lignes['lest_anti_glissement']
        self.assertIsNone(glissement['valeur'],
                          "Un coefficient non saisi doit laisser la ligne NON "
                          "calculée, jamais une valeur par défaut.")
        self.assertIn('coefficient_frottement', glissement['manquants'])
        self.assertIn('Coefficient de frottement', glissement['mention'])
        # Les lignes qui ne dépendent PAS du coefficient absent, elles, sont
        # servies : une saisie partielle n'éteint pas toute la feuille.
        self.assertIsNotNone(lignes['pression_dynamique']['valeur'])


class PorteMasseLestageTest(SimpleTestCase):
    """L'action elle-même, appelée hors de toute requête HTTP."""

    def _appeler(self, **parametres):
        from apps.calepinage.views.sorties import SortiesMixin

        class Vue(SortiesMixin, FauxViewSet):
            pass

        return SortiesMixin.masse_lestage(
            Vue(CalepinageNu()), FausseRequete(**parametres), pk=1)

    def test_la_porte_rend_la_sortie_du_service_telle_quelle(self):
        reponse = self._appeler()
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, _contrat()['exemple_vide'])

    def test_un_module_non_numerique_est_refuse_en_nommant_le_champ(self):
        reponse = self._appeler(module='panneau-550')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('module', reponse.data,
                      "Le refus doit NOMMER le champ fautif : un « non "
                      "enregistré » générique n'est pas actionnable.")
        self.assertIn('panneau-550', reponse.data['module'])


# ── ACAL564 — centre, rive, coin : le lest ADDITIONNEL par module ──────────

def _zones_saisies(**valeurs):
    """Les quatre paramètres ``zones_de_pose`` saisis avec leur source."""
    defaut = {'largeur_bande_rive_m': 1.0, 'largeur_coin_m': 0.8,
              'lest_rive_kg_par_module': 12.5,
              'lest_coin_kg_par_module': 25.0}
    defaut.update(valeurs)
    return {cle: {'valeur': v, 'source': 'notice K2 (essai)'}
            for cle, v in defaut.items() if v is not None}


def _pan_4x6():
    return {'repere': 'PAN-1',
            'points': [(0.0, 0.0), (4.0, 0.0), (4.0, 6.0), (0.0, 6.0)],
            'modules': [(0.5 + i, 0.5 + j)
                        for i in range(4) for j in range(6)]}


class RepartitionDuLestageTest(SimpleTestCase):

    def test_4x6_donne_4_coins_12_rives_8_centres(self):
        from apps.calepinage.services.lestage_zones import repartir_modules

        sortie = repartir_modules([_pan_4x6()], _zones_saisies())
        self.assertTrue(sortie['disponible'])
        self.assertEqual(sortie['manquants'], [])
        pan = sortie['pans'][0]
        self.assertEqual((pan['coins'], pan['rives'], pan['centres']),
                         (4, 12, 8))
        self.assertEqual(pan['lest_kg'], 4 * 25.0 + 12 * 12.5)
        self.assertEqual(sortie['total_lest_kg'], pan['lest_kg'])
        par_centre = {tuple(m['centre']): m for m in pan['modules']}
        self.assertEqual(par_centre[(0.5, 0.5)]['zone'], 'coin')
        self.assertEqual(par_centre[(1.5, 0.5)]['zone'], 'rive')
        self.assertEqual(par_centre[(1.5, 1.5)],
                         {'centre': [1.5, 1.5], 'zone': 'centre',
                          'lest_kg': 0.0})

    def test_la_bande_est_inclusive(self):
        from apps.calepinage.services.lestage_zones import repartir_modules

        # (1.5, 1.5) est à 1,5 m de la rive : une bande de 1,5 m l'y range.
        pan = repartir_modules([_pan_4x6()], _zones_saisies(
            largeur_bande_rive_m=1.5))['pans'][0]
        self.assertEqual(pan['centres'], 0)

    def test_un_parametre_manquant_rend_indisponible_en_le_nommant(self):
        from apps.calepinage.services.lestage_zones import repartir_modules

        sortie = repartir_modules([_pan_4x6()],
                                  _zones_saisies(largeur_coin_m=None))
        self.assertFalse(sortie['disponible'])
        self.assertEqual([m['cle'] for m in sortie['manquants']],
                         ['largeur_coin_m'])
        self.assertEqual(sortie['pans'], [])
        self.assertIsNone(sortie['total_lest_kg'])

    def test_aucun_module_rend_vide(self):
        from apps.calepinage.services.lestage_zones import repartir_modules

        pan = dict(_pan_4x6(), modules=[])
        sortie = repartir_modules([pan], _zones_saisies())
        self.assertEqual(sortie['pans'], [])
        self.assertEqual(sortie['total_lest_kg'], 0.0)
