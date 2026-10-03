"""AGR122 — les clés ``etude_params`` du pompage v2 déclarées au schéma.

CE QUI ÉTAIT FAUX. Le bloc agricole de ``domain/etude_schema.py`` déclarait
``pompe_cv``/``pompe_kw`` comme ENTRÉES d'écran et ``m3_jour``/``champ_kwc``/
``debit_hmt_m3h`` comme dérivées… de l'écran. En production, les 23 devis
agricoles portent des DÉFAUTS enregistrés comme des mesures (``distance_m=20``,
``alim=tri``, ``type_pompe=immergee`` partout).

CE QUE CES TESTS TIENNENT (Done d'AGR122) :

1. chaque clé de ``cles_etude_params_v2`` du contrat partagé
   ``contract_samples/etude_pompage_preview.json`` est déclarée avec le BON
   propriétaire (ENTRÉES = ``ecran`` ; DÉRIVÉES = ``moteur_pompage``) ;
2. une clé inconnue — dont les anciennes clés v1 retirées (D-AGR-13) — est
   refusée en 400 FR qui la NOMME ;
3. une dérivée envoyée par le navigateur est refusée ;
4. chaque dérivée du moteur est purgée des copies (``CLES_DERIVEES_NON_COPIEES``),
   et la règle QJR117 (chaque clé purgée est DÉRIVÉE au schéma) reste vraie.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agr122_etude_schema_pompage -v 2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.ventes.domain import etude_schema as S
from apps.ventes.domain.etudes import CLES_DERIVEES_NON_COPIEES

CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'etude_pompage_preview.json')

#: Les clés v1 du bloc agricole qui QUITTENT le schéma (contrat › regle_v1).
CLES_V1_RETIREES = (
    'current_fuel', 'fuel_spend_current', 'distance_m', 'hmt_static',
    'hmt_drawdown', 'region', 'crop', 'surface_ha', 'profondeur_m',
    'debit_souhaite_m3h', 'irrigation_method',
)


def _cles_v2():
    with CONTRAT.open(encoding='utf-8') as fichier:
        return json.load(fichier)['cles_etude_params_v2']


def _derivees(v2):
    return list(v2['derivees']) + list(v2['derivees_v1_lues_par_le_rendu'])


class SchemaPompageV2Tests(SimpleTestCase):

    def test_le_proprietaire_moteur_pompage_existe(self):
        self.assertEqual(S.MOTEUR_POMPAGE, 'moteur_pompage')

    def test_chaque_entree_du_contrat_est_une_ENTREE_ecran(self):
        for item in _cles_v2()['entrees']:
            with self.subTest(cle=item['cle']):
                regle = S.SCHEMA.get(item['cle'])
                self.assertIsNotNone(regle, 'clé absente du schéma')
                self.assertEqual(item['proprietaire'], S.ECRAN)
                self.assertEqual(regle['proprietaire'], S.ECRAN)
                self.assertEqual(regle['nature'], S.ENTREE)

    def test_chaque_derivee_du_contrat_appartient_au_moteur_pompage(self):
        for item in _derivees(_cles_v2()):
            with self.subTest(cle=item['cle']):
                regle = S.SCHEMA.get(item['cle'])
                self.assertIsNotNone(regle, 'clé absente du schéma')
                self.assertEqual(item['proprietaire'], S.MOTEUR_POMPAGE)
                self.assertEqual(regle['proprietaire'], S.MOTEUR_POMPAGE)
                self.assertEqual(regle['nature'], S.DERIVEE)

    def test_le_schema_ne_declare_aucune_derivee_moteur_hors_contrat(self):
        du_contrat = {c['cle'] for c in _derivees(_cles_v2())}
        du_schema = {cle for cle, r in S.SCHEMA.items()
                     if r['proprietaire'] == S.MOTEUR_POMPAGE}
        self.assertEqual(du_schema, du_contrat)

    def test_les_cles_v1_retirees_ne_sont_plus_au_schema(self):
        for cle in CLES_V1_RETIREES:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, S.SCHEMA)

    def test_une_cle_inconnue_est_refusee_et_nommee(self):
        for cle in CLES_V1_RETIREES + ('pompe_nom',):
            with self.subTest(cle=cle):
                reproches = S.valider({cle: 1})
                self.assertEqual(len(reproches), 1)
                self.assertIn('« %s »' % cle, reproches[0])

    def test_une_derivee_ecrite_par_l_ecran_est_refusee(self):
        for item in _derivees(_cles_v2()):
            with self.subTest(cle=item['cle']):
                self.assertEqual(
                    S.cles_refusees_pour(S.ECRAN, [item['cle']]),
                    [item['cle']])
                with self.assertRaises(ValueError) as ctx:
                    S.fusionner({}, proprietaire=S.ECRAN,
                                **{item['cle']: {}})
                self.assertIn(item['cle'], str(ctx.exception))

    def test_le_moteur_pompage_peut_ecrire_ses_derivees(self):
        bloc = S.fusionner(
            {'mode_pompe': 'neuve'}, proprietaire=S.MOTEUR_POMPAGE,
            m3_jour=135.0, pompe_kw=7.5, production={'mode': 'courbe'},
            couverture_pct_mois=[100] * 12, alertes_pompage=[])
        self.assertEqual(bloc['m3_jour'], 135.0)
        self.assertEqual(bloc['mode_pompe'], 'neuve')

    def test_les_entrees_v2_de_l_ecran_passent(self):
        corps = {
            'mode_pompe': 'neuve', 'plaque': None,
            'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
            'source': {'debit_exploitation_m3h': 36},
            'hmt_entrees': {'saisie_m': None, 'denivele_m': 4},
            'alim': 'tri', 'type_pompe': 'immergee',
            'localisation': {'ville': 'Taroudant'},
            'distance_champ_m': 25,
            'options_cochees': ['afficheur_variateur'],
            'taille': 'recommandee',
        }
        self.assertEqual(S.cles_refusees_pour(S.ECRAN, corps), [])
        self.assertEqual(S.valider(corps), [])

    def test_chaque_derivee_moteur_est_purgee_des_copies(self):
        for item in _derivees(_cles_v2()):
            with self.subTest(cle=item['cle']):
                self.assertIn(item['cle'], CLES_DERIVEES_NON_COPIEES)

    def test_la_regle_qjr117_tient_avec_les_nouvelles_derivees(self):
        for cle in CLES_DERIVEES_NON_COPIEES:
            with self.subTest(cle=cle):
                self.assertEqual(S.SCHEMA[cle]['nature'], S.DERIVEE)


class EndpointFusionPompageTests(TestCase):
    """Le même refus, vu du navigateur : ``PATCH /devis/<id>/etude-params/``."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from authentication.models import CustomUser
        from testkit.factories import CompanyFactory, DevisFactory, UserFactory

        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company,
                                role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.devis = DevisFactory(company=self.company,
                                  mode_installation='agricole',
                                  etude_params={})
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/ventes/devis/{self.devis.id}/etude-params/'

    def test_une_ancienne_cle_v1_est_refusee_en_400_qui_la_nomme(self):
        resp = self.api.patch(self.url, {'current_fuel': 'butane'},
                              format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('current_fuel', resp.data['detail'])

    def test_une_derivee_du_moteur_envoyee_par_l_ecran_est_refusee(self):
        resp = self.api.patch(self.url, {'m3_jour': 86.8}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('m3_jour', resp.data['detail'])
        self.devis.refresh_from_db()
        self.assertNotIn('m3_jour', self.devis.etude_params or {})

    def test_une_entree_v2_de_l_ecran_est_fusionnee(self):
        resp = self.api.patch(
            self.url, {'mode_pompe': 'neuve', 'taille': 'recommandee'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['etude_params']['mode_pompe'], 'neuve')
