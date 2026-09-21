# -*- coding: utf-8 -*-
"""CALX228 — LES TRONÇONS SERVIS EN HTTP, ET JOINTS AU RÉSULTAT.

LE CONSTAT
----------
``views/electrique.py`` n'exposait que trois actions (``resultat``,
``entree-electrique``, ``evaluer-electrique``) et ``resultat['cables']`` ne
portait que les deux lignes historiques : ``services/troncons.py``
(CALX224-226) était construit, testé, et INJOIGNABLE. Parité : HelioScope
sert son SLD et ses conducteurs comme une vue vivante du design
(https://help-center.helioscope.com/hc/en-us/articles/
8198335127059-Single-Line-Diagram).

TROIS ÉTAGES, TROIS COÛTS
-------------------------
1. :class:`RoutageTronconsTest` — l'action est RÉELLEMENT enregistrée sur le
   viewset pivot, son ``__name__`` égale le nom d'attribut (piège de classe
   #105 : un alias fait disparaître la route en silence), et sa garde est
   celle de la LECTURE ;
2. :class:`ContratTronconsTest` et :class:`RattachementDesCourantsTest`
   (``SimpleTestCase``) — la charge utile est épinglée CLÉ POUR CLÉ sur
   l'échantillon committé, et le rattachement des chaînes aux tronçons est
   armé sur le cas qui le motive (un tronçon amont qui cumule, un tronçon
   terminal qui ne cumule pas) ;
3. :class:`TronconsApiTest` (``APITestCase``) — 200 à la forme du contrat,
   404 pour un calepinage d'une AUTRE société, et aucune écriture. **Ce
   dernier étage exige la base : il n'a PAS été exécuté sur le poste de la
   lane, la CI en est le juge.**

Run :
    python manage.py test apps.calepinage.tests.test_calx228_api_troncons -v2
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services.troncons import (
    _contexte_electrique, _troncons_du_document, metre_de_cable,
)
from core.electrique.chaines import concevoir_chaines
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / 'contract_samples' / 'calepinage_troncons.json'

#: Les QUATRE clés racines du contrat CALX203 — la garde de forme.
CLES_DU_CONTRAT = ('troncons', 'totaux', 'omissions', 'verdicts')

MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=500.0,
                        v_max_abs=600.0, i_max_mppt_a=26.0, ac_kw=5.0,
                        phases=1, designation='Deye SG05LP3')

#: La norme, telle que ``norme_applicable`` la rend quand une société en a
#: choisi une : ce test ne pose AUCUN barème, il reprend les clés du registre.
NORME_FR = {
    'applicable': True,
    'coefficients': {
        'coeff_isc_dimensionnement': {
            'valeur': 1.25,
            'reference': 'IEC 62548 §7.3 — courant de dimensionnement DC'},
        'chute_dc_cible_pct': {
            'valeur': 1.0, 'reference': 'UTE C 15-712-1 — chute DC, cible'},
        'chute_dc_max_pct': {
            'valeur': 3.0, 'reference': 'UTE C 15-712-1 — chute DC, maximum'},
        'section_min_dc_mm2': {
            'valeur': 6.0, 'reference': 'décision fondateur 19/08/2026'},
    },
}


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode."""
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


def _conception(nb_modules=12):
    """Une conception PURE : deux pans, des chaînes réelles, aucune base."""
    entree = EntreeElectrique(
        module=MODULE, onduleur=ONDULEUR,
        groupes=(GroupePan(label='PAN-A', nb_modules=nb_modules,
                           azimut_deg=180.0, inclinaison_deg=15.0),),
        dc_m=30.0, ac_m=12.0, phases=1)

    class _Conception:
        pass

    conception = _Conception()
    conception.entree = entree
    conception.resultat = concevoir_chaines(entree)
    conception.chaines = conception.resultat.chaines
    conception.fiche_incomplete = False
    conception.manquantes = ()
    return conception


def _document(cheminements):
    return {'electrical': {'cheminements': list(cheminements)}}


class RoutageTronconsTest(SimpleTestCase):
    """Sans route, l'onglet « Cheminement & câbles » appellerait dans le vide."""

    def test_l_action_est_enregistree_sur_le_pivot(self):
        _viewset, actions = _actions()
        self.assertIn(
            'troncons', actions,
            "L'action « troncons » n'est pas rattachée au CalepinageViewSet "
            '— vérifier la ligne ajoutée en fin de views/rattachements.py '
            '(CALX228).')
        self.assertEqual(actions['troncons'].url_path, 'troncons')
        self.assertTrue(actions['troncons'].detail)
        self.assertEqual(set(actions['troncons'].mapping), {'get'})

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        """DRF mappe par ``__name__`` — un alias serait ignoré (bug #105)."""
        viewset, _actions_ = _actions()
        self.assertEqual(getattr(viewset, 'troncons').__name__, 'troncons')

    def test_aucune_autre_action_ne_porte_ce_nom(self):
        # Collision de noms d'action : deux modules qui greffent le même
        # attribut, et la seconde greffe écrase la première SANS bruit.
        _viewset, actions = _actions()
        noms = [methode.__name__
                for methode in actions.values()]
        self.assertEqual(noms.count('troncons'), 1)
        chemins = [methode.url_path for methode in actions.values()]
        self.assertEqual(chemins.count('troncons'), 1)

    def test_la_garde_est_celle_de_la_lecture(self):
        _viewset, actions = _actions()
        self.assertEqual(
            [garde.__name__
             for garde in actions['troncons'].kwargs['permission_classes']],
            ['PeutVoirCalepinage'])

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('troncons', MODULES_RATTACHES)
        # EN FIN, jamais au milieu (surface append-only, D-CALX 13).
        self.assertEqual(MODULES_RATTACHES[-1], 'troncons')

    def test_le_chemin_resout_sous_le_calepinage(self):
        from django.urls import reverse

        self.assertEqual(
            reverse('calepinage-troncons', args=('1',)),
            '/api/django/calepinage/calepinages/1/troncons/')


class ContratTronconsTest(SimpleTestCase):
    """La charge utile est celle de l'échantillon committé, clé pour clé."""

    def test_l_etat_vide_porte_les_quatre_cles(self):
        servi = _troncons_du_document({'electrical': {'cheminements': []}})
        self.assertEqual(sorted(servi), sorted(CLES_DU_CONTRAT))
        self.assertEqual(sorted(servi),
                         sorted(_contrat()['exemple_vide']))

    def test_l_etat_servi_porte_les_quatre_cles(self):
        servi = _troncons_du_document(_document([
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-A', 'vers': 'eq2',
             'longueurSaisieM': 18.4},
        ]), _contexte_electrique(_conception(), NORME_FR))
        self.assertEqual(sorted(servi), sorted(CLES_DU_CONTRAT))
        self.assertEqual(sorted(servi), sorted(_contrat()['exemple']))

    def test_les_totaux_portent_les_trois_cles_du_contrat(self):
        servi = _troncons_du_document({'electrical': {'cheminements': []}})
        self.assertEqual(sorted(servi['totaux']),
                         sorted(_contrat()['exemple']['totaux']))

    def test_un_troncon_publie_les_quatorze_champs_du_contrat(self):
        servi = _troncons_du_document(_document([
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-A', 'vers': 'eq2',
             'longueurSaisieM': 18.4},
        ]), _contexte_electrique(_conception(), NORME_FR))
        self.assertEqual(sorted(servi['troncons'][0]),
                         sorted(_contrat()['exemple']['troncons'][0]))

    def test_une_omission_nomme_troncon_champ_et_motif(self):
        servi = _troncons_du_document({'electrical': {'cheminements': []}})
        self.assertEqual(sorted(servi['omissions'][0]),
                         sorted(_contrat()['exemple_vide']['omissions'][0]))

    def test_l_echantillon_n_est_plus_pose_avant_sa_route(self):
        from apps.calepinage.tests.test_cal223_contrats import (
            POSES_AVANT_LEUR_ROUTE,
        )

        self.assertNotIn('calepinage_troncons.json', POSES_AVANT_LEUR_ROUTE)


class RattachementDesCourantsTest(SimpleTestCase):
    """CALX228 — un tronçon amont ne prend plus le courant du côté."""

    def _courants(self, cheminements, conception=None):
        conception = conception or _conception()
        return _contexte_electrique(conception, NORME_FR,
                                    cheminements)['courants']

    def test_les_chaines_declarees_rattachent_leur_courant(self):
        conception = _conception()
        toutes = [chaine.repere for chaine in conception.chaines]
        courants = self._courants([
            {'id': 'amont', 'cote': 'dc', 'de': 'eq1', 'vers': 'eq2',
             'chaines': toutes},
            {'id': 'terminal', 'cote': 'dc', 'de': 'eq2', 'vers': 'eq3',
             'chaines': toutes[:1]},
        ], conception)
        self.assertIn('amont', courants)
        self.assertIn('terminal', courants)
        # Le tronçon AMONT porte plus de courant que le terminal dès que la
        # conception a plus d'une chaîne ; sinon les deux sont égaux — dans
        # les deux cas, aucun ne « prend le courant du côté ».
        if len(toutes) > 1:
            self.assertGreater(courants['amont']['ib_a'],
                               courants['terminal']['ib_a'])
        else:
            self.assertEqual(courants['amont']['ib_a'],
                             courants['terminal']['ib_a'])

    def test_le_calibre_n_est_publie_que_pour_une_seule_chaine(self):
        conception = _conception()
        toutes = [chaine.repere for chaine in conception.chaines]
        if len(toutes) < 2:
            self.skipTest('la conception d essai ne pose qu une chaîne')
        courants = self._courants([
            {'id': 'amont', 'cote': 'dc', 'de': 'eq1', 'vers': 'eq2',
             'chaines': toutes},
        ], conception)
        self.assertIsNone(courants['amont']['calibre_in_a'])

    def test_le_pan_amont_rattache_ses_chaines(self):
        courants = self._courants([
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-A', 'vers': 'eq2'},
        ])
        self.assertIn('ch1', courants)
        self.assertGreater(courants['ch1']['ib_a'], 0.0)
        self.assertGreater(courants['ch1']['tension_v'], 0.0)

    def test_un_pan_inconnu_ne_rattache_rien(self):
        # Rien n'est inventé : le tronçon retombe sur le courant du CÔTÉ,
        # exactement comme avant CALX228.
        self.assertEqual(self._courants([
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-INCONNU', 'vers': 'eq2'},
        ]), {})

    def test_un_repere_de_chaine_inconnu_ne_rattache_rien(self):
        self.assertEqual(self._courants([
            {'id': 'ch1', 'cote': 'dc', 'de': 'eq1', 'vers': 'eq2',
             'chaines': ['CH999']},
        ]), {})

    def test_une_branche_ac_rattache_son_courant(self):
        contexte = _contexte_electrique(
            _conception(), NORME_FR,
            [{'id': 'ac1', 'cote': 'ac', 'de': 'BR2', 'vers': 'eq9'}],
            branches_ac=[
                {'repere': 'BR1', 'i_branche_a': 4.0, 'calibre_a': 16.0},
                {'repere': 'BR2', 'i_branche_a': 9.5, 'calibre_a': 20.0},
            ])
        self.assertEqual(contexte['courants']['ac1']['ib_a'], 9.5)
        self.assertEqual(contexte['courants']['ac1']['calibre_in_a'], 20.0)

    def test_une_branche_sans_courant_publie_ne_rattache_rien(self):
        contexte = _contexte_electrique(
            _conception(), NORME_FR,
            [{'id': 'ac1', 'cote': 'ac', 'de': 'BR1', 'vers': 'eq9'}],
            branches_ac=[{'repere': 'BR1', 'i_branche_a': None,
                          'calibre_a': None}])
        self.assertEqual(contexte['courants'], {})

    def test_le_rattachement_change_la_section_du_troncon(self):
        # La preuve que le crochet SERT : deux tronçons du même côté, deux
        # courants, donc deux dimensionnements — c'est ce que CALX225 ne
        # pouvait pas faire sans lui.
        conception = _conception()
        toutes = [chaine.repere for chaine in conception.chaines]
        if len(toutes) < 2:
            self.skipTest('la conception d essai ne pose qu une chaîne')
        servi = _troncons_du_document(_document([
            {'id': 'amont', 'cote': 'dc', 'de': 'eq1', 'vers': 'eq2',
             'longueurSaisieM': 40.0, 'chaines': toutes},
            {'id': 'terminal', 'cote': 'dc', 'de': 'eq2', 'vers': 'eq3',
             'longueurSaisieM': 40.0, 'chaines': toutes[:1]},
        ]), _contexte_electrique(conception, NORME_FR, [
            {'id': 'amont', 'cote': 'dc', 'de': 'eq1', 'vers': 'eq2',
             'chaines': toutes},
            {'id': 'terminal', 'cote': 'dc', 'de': 'eq2', 'vers': 'eq3',
             'chaines': toutes[:1]},
        ]))
        par_id = {troncon['id']: troncon for troncon in servi['troncons']}
        self.assertGreater(par_id['amont']['ib_a'],
                           par_id['terminal']['ib_a'])

    def test_le_metre_suit_les_sections_ainsi_rattachees(self):
        servi = _troncons_du_document(_document([
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-A', 'vers': 'eq2',
             'longueurSaisieM': 18.4},
        ]), _contexte_electrique(_conception(), NORME_FR, [
            {'id': 'ch1', 'cote': 'dc', 'de': 'PAN-A', 'vers': 'eq2'},
        ]))
        lignes = metre_de_cable(servi['troncons'])
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['repere_des_troncons'], ['ch1'])


class TronconsApiTest(TestCase):
    """L'API réelle — EXIGE LA BASE, non exécutée sur le poste de la lane.

    Elle arme les trois promesses du « Done » de CALX228 : 200 à la forme du
    contrat, 404 pour un calepinage d'une AUTRE société (introuvable, jamais
    « interdit »), et AUCUNE écriture (le statut ne bouge pas).
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
        from authentication.models import Company

        # Même patron que ``test_api_liste`` : deux sociétés, un porteur des
        # droits (``calepinage_voir``), un lead par calepinage (contrainte
        # ``calepinage_lead_ou_client``), authentification par jeton.
        self.company = Company.objects.create(nom='Troncons Co',
                                              slug='troncons-co-228')
        self.autre = Company.objects.create(nom='Voisine Co',
                                            slug='voisine-co-228')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='poseur_228', password='x', company=self.company,
            role=role)
        lead = Lead.objects.create(company=self.company, nom='Toiture A')
        lead_autre = Lead.objects.create(company=self.autre,
                                         nom='Toiture B')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Toiture A',
            roof_layout={'version': 2, 'zones': []})
        self.calepinage_autre = Calepinage.objects.create(
            company=self.autre, lead_id=lead_autre.pk, titre='Toiture B',
            roof_layout={'version': 2, 'zones': []})
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, calepinage):
        return ('/api/django/calepinage/calepinages/%d/troncons/'
                % calepinage.pk)

    def test_200_a_la_forme_du_contrat(self):
        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(sorted(reponse.json()), sorted(CLES_DU_CONTRAT))

    def test_404_pour_un_calepinage_d_une_autre_societe(self):
        reponse = self.client.get(self._url(self.calepinage_autre))

        self.assertEqual(reponse.status_code, 404)

    def test_aucune_ecriture(self):
        avant = (self.calepinage.statut, self.calepinage.updated_at,
                 self.calepinage.resultat)

        self.client.get(self._url(self.calepinage))

        self.calepinage.refresh_from_db()
        self.assertEqual(
            (self.calepinage.statut, self.calepinage.updated_at,
             self.calepinage.resultat), avant)
