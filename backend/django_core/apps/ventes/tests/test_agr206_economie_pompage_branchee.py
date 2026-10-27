# -*- coding: utf-8 -*-
"""AGR206 — l'économie de pompage branchée : lecture du devis, deux
endpoints, clé d'étude déclarée, lecture publique pour les autres apps.

Réseau : PVGIS et TMY simulés (patron AGR121) — aucun test ne touche le
réseau.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr206_economie_pompage_branchee"
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import economie_pompage as E
from apps.ventes import selectors
from apps.ventes.domain import etude_schema as es
from apps.ventes.domain import pompage
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests.test_agr_economie_pompage import (
    CHARGES, ETUDE_COUVERTE, REPERES, etude_declaree, lignes_reference,
    saisies_12000, saisies_carburant)
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'economie_pompage.json').read_text(encoding='utf-8'))
SAISIES = CONTRAT['saisies_economie_pompage']['exemple']

_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]


def _cles(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _cles(v)


class SchemaTests(SimpleTestCase):
    def test_la_cle_passe_valider(self):
        self.assertEqual(es.valider({'saisies_economie_pompage': SAISIES}), [])
        self.assertEqual(
            es.cles_refusees_pour(es.ECRAN, ['saisies_economie_pompage']), [])

    def test_anciennes_cles_carburant_retirees(self):
        for cle in ('current_fuel', 'fuel_spend_current'):
            self.assertNotIn(cle, es.SCHEMA)
            reproches = es.valider({cle: 'butane'})
            self.assertTrue(reproches and cle in reproches[0])

    def test_aller_retour_identique(self):
        bloc = es.fusionner({'mode_installation': 'agricole'},
                            proprietaire=es.ECRAN,
                            saisies_economie_pompage=SAISIES)
        rouvert = json.loads(json.dumps(bloc))
        bloc2 = es.fusionner(
            rouvert, proprietaire=es.ECRAN,
            saisies_economie_pompage=rouvert['saisies_economie_pompage'])
        self.assertEqual(bloc2, bloc)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr206-co', defaults={'nom': 'AGR206 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='agr206-autre', defaults={'nom': 'AGR206 Autre'})[0]
        cls.client_crm = Client.objects.create(
            company=cls.co, nom='Ferme', prenom='AGR206',
            email='agr206@example.com', telephone='+212600000206')
        cls.devis = Devis.objects.create(
            company=cls.co, reference='DEV-AGR206-1', client=cls.client_crm,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            mode_installation='agricole',
            etude_params={'saisies_economie_pompage': SAISIES})
        produit = Produit.objects.create(
            company=cls.co, nom='Pompe immergée 5.5 kW', sku='AGR206-P',
            role_pompage='pompe', prix_vente=Decimal('18000'),
            prix_achat=Decimal('9999'))
        LigneDevis.objects.create(
            devis=cls.devis, produit=produit, designation=produit.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('18000'),
            remise=Decimal('0'), taux_tva=Decimal('10'))
        cls.produit = produit

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr206_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)


class LectureTests(_Base):
    def test_get_forme_du_contrat(self):
        rep = self.api.get(
            f'/api/django/ventes/devis/{self.devis.pk}/economie-pompage/')
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        self.assertEqual(set(rep.json()), set(CONTRAT['exemple']))
        self.assertIn('vue_interne', rep.json())

    def test_donnee_du_devis_refusee_409(self):
        # CI #997 fuzz (24/10) : la requête (GET sans corps) est conforme ;
        # c'est une grandeur STOCKÉE du devis que le calcul refuse = refus
        # d'état 409 qui nomme le champ, plus un 400.
        from apps.ventes.economie import EconomieInvalide
        with mock.patch(
                'apps.ventes.views.economie_pompage.'
                'economie_pompage_pour_devis',
                side_effect=EconomieInvalide(
                    'lignes[0].total_ttc_mad : -1 refusé',
                    champ='lignes[0].total_ttc_mad')):
            rep = self.api.get(
                f'/api/django/ventes/devis/{self.devis.pk}/economie-pompage/')
        self.assertEqual(rep.status_code, 409, rep.content[:500])
        self.assertIn('lignes[0].total_ttc_mad', str(rep.json()))

    def test_autre_societe_404(self):
        etranger = User.objects.create_user(
            username='agr206_etranger', password='x',
            role_legacy='responsable', company=self.autre)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(etranger)}')
        rep = api.get(
            f'/api/django/ventes/devis/{self.devis.pk}/economie-pompage/')
        self.assertEqual(rep.status_code, 404)

    def test_corps_tableau_400(self):
        # CI #997 — un corps hors schéma (``[null, null]``) répondait 200
        # (calcul « omis ») : 400.
        rep = self.api.post('/api/django/ventes/economie-pompage/preview/', [None, None], format='json')
        self.assertEqual(rep.status_code, 400, rep.content)

    def test_preview_n_ecrit_rien(self):
        avant = Devis.objects.get(pk=self.devis.pk)
        rep = self.api.post(
            '/api/django/ventes/economie-pompage/preview/',
            {'saisies': SAISIES, 'sortie_etude_pompage': None,
             'lignes': [{'produit': self.produit.pk, 'quantite': 1,
                         'prix_unitaire': 18000, 'remise': 0,
                         'taux_tva': 10}]}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        self.assertEqual(set(rep.json()), set(CONTRAT['exemple']))
        apres = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(apres.etude_params, avant.etude_params)
        self.assertEqual(apres.statut, avant.statut)
        self.assertEqual(apres.updated_at, avant.updated_at)

    def test_selecteur_public_sans_vue_interne_ni_prix_achat(self):
        bloc = selectors.economie_pompage_publique_pour_devis(
            self.devis.pk, self.co)
        self.assertIsNotNone(bloc)
        self.assertNotIn('vue_interne', bloc)
        cles = set(_cles(bloc))
        self.assertNotIn('prix_achat', cles)
        self.assertNotIn('9999', json.dumps(bloc))
        self.assertIsNone(selectors.economie_pompage_publique_pour_devis(
            self.devis.pk, self.autre))
        self.assertIsInstance(
            selectors.economie_pompage_publiable(self.devis.pk, self.co),
            bool)


MOTIF_COUVERTURE = 'couverture non vérifiable : pompe sans courbe'


class AGM9CouvertureNonVerifiableTests(SimpleTestCase):
    """AGM9 (D-AGM-3) — une couverture supposée ne fonde aucun chiffre
    client ; l'aperçu vendeur garde ses chiffres."""

    def bloc(self, sortie_etude, saisies=None):
        return E.economie_pompage(
            saisies or saisies_12000(), sortie_etude=sortie_etude,
            lignes=lignes_reference(), reglages=CHARGES)

    def test_pompe_sans_courbe_non_publiable_avec_motif(self):
        bloc = self.bloc({'pompe': {'mode': 'neuve'}})
        self.assertFalse(bloc['couverture']['verifiee'])
        self.assertFalse(bloc['publiable_client'])
        self.assertIn(MOTIF_COUVERTURE, bloc['motifs_non_publiable'])
        # L'écran vendeur garde l'aperçu chiffré.
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['economie']['retour_ans'], 5)

    def test_etude_couverte_inchangee(self):
        bloc = self.bloc(ETUDE_COUVERTE)
        self.assertTrue(bloc['publiable_client'])
        self.assertNotIn(MOTIF_COUVERTURE, bloc['motifs_non_publiable'])

    def test_nouveau_forage_reste_publiable(self):
        saisies = {'energie_actuelle': {
            'valeur': 'aucune', 'provenance': {
                'origine': 'saisie', 'detail': None, 'date': '2026-09-12'}},
            'consommation': {'jours_irrigation_par_semaine': 7},
            'mois_irrigation': {'mois': list(range(1, 13)), 'provenance': {
                'origine': 'saisie', 'detail': None, 'date': '2026-09-12'}}}
        bloc = self.bloc({'pompe': {'mode': 'neuve'}}, saisies=saisies)
        self.assertEqual(bloc['cas'], 'nouveau_forage')
        self.assertNotIn(MOTIF_COUVERTURE, bloc['motifs_non_publiable'])
        self.assertTrue(bloc['publiable_client'])


class AGM10SansBaremeTests(SimpleTestCase):
    """AGM10 — barème des charges solaires absent : seuil, sensibilité, coût
    du m³ solaire, retour et scénario butane OMIS (jamais calculés avec un
    entretien à 0)."""

    @staticmethod
    def gasoil():
        # 10 L par jour d'irrigation x 6 j/semaine, 12 MAD/L, avril-sept.
        return saisies_carburant(
            energie='diesel', quantite=10, unite='litre',
            periode='jour_irrigation', jours=6, prix=12.0,
            mois=range(4, 10))

    def bloc(self, reglages, saisies=None, **kw):
        kw.setdefault('sortie_etude', etude_declaree())
        return E.economie_pompage(
            saisies or self.gasoil(), lignes=lignes_reference(),
            reglages=reglages, **kw)

    def test_sans_bareme_chaque_chiffre_dependant_est_omis(self):
        for reglages in ({}, None):
            with self.subTest(reglages=reglages):
                bloc = self.bloc(reglages)
                self.assertIsNone(bloc['seuil_rentabilite_carburant'])
                self.assertIn('seuil_rentabilite_carburant',
                              [o['cle'] for o in bloc['omissions']])
                self.assertEqual(len(bloc['sensibilite_carburant']), 5)
                for ligne in bloc['sensibilite_carburant']:
                    self.assertIsNone(ligne['economie_nette_mad_an'])
                    self.assertIsNone(ligne['retour_ans'])
                self.assertIsNone(bloc['mad_par_m3']['solaire'])
                self.assertIn('mad_par_m3.solaire',
                              [o['cle'] for o in bloc['omissions']])
                eco = bloc['economie']
                self.assertIsNone(eco['retour_ans'])
                self.assertEqual(eco['flux'], [])
                self.assertIsNone(eco['economie_nette_an1'])
                self.assertIn('charges_annuelles_mad',
                              [o['cle'] for o in eco['omissions']])
                self.assertFalse(bloc['publiable_client'])

    def test_forme_inchangee_avec_ou_sans_bareme(self):
        avec = self.bloc(CHARGES)
        sans = self.bloc({})
        self.assertEqual(set(avec), set(sans))
        self.assertEqual(set(avec['economie']), set(sans['economie']))
        self.assertEqual(set(avec['sensibilite_carburant'][0]),
                         set(sans['sensibilite_carburant'][0]))
        self.assertEqual(set(avec['mad_par_m3']), set(sans['mad_par_m3']))

    def test_avec_bareme_inchange(self):
        bloc = self.bloc(CHARGES)
        self.assertIsNotNone(bloc['seuil_rentabilite_carburant'])
        self.assertIsNotNone(bloc['mad_par_m3']['solaire'])
        self.assertEqual(len(bloc['economie']['flux']), 11)
        self.assertIsNotNone(bloc['economie']['economie_nette_an1'])
        for ligne in bloc['sensibilite_carburant']:
            self.assertIsNotNone(ligne['economie_nette_mad_an'])

    def test_nouveau_forage_sans_bareme_m3_solaire_omis(self):
        horodatage = {'origine': 'saisie', 'detail': None,
                      'date': '2026-09-12'}
        saisies = {'energie_actuelle': {'valeur': 'aucune',
                                        'provenance': horodatage},
                   'consommation': {'jours_irrigation_par_semaine': 7},
                   'mois_irrigation': {'mois': list(range(1, 13)),
                                       'provenance': horodatage}}
        bloc = self.bloc({}, saisies=saisies,
                         sortie_etude=etude_declaree(volume=50.0,
                                                     production=40.0))
        self.assertEqual(bloc['cas'], 'nouveau_forage')
        self.assertIsNone(bloc['mad_par_m3']['solaire'])
        self.assertFalse(bloc['publiable_client'])

    def test_vue_interne_scenario_butane_et_van_omis(self):
        saisies = saisies_carburant()
        saisies['taux_actualisation'] = {'valeur': 8, 'source': 'banque'}
        sans = self.bloc({}, saisies=saisies, reperes=REPERES)
        interne = sans['vue_interne']
        self.assertIsNone(interne['scenario_butane_non_subventionne'])
        self.assertIsNone(interne['van_mad'])
        cles = [o['cle'] for o in interne['omissions']]
        self.assertIn('scenario_butane_non_subventionne', cles)
        self.assertIn('van_mad', cles)
        avec = self.bloc(CHARGES, saisies=saisies, reperes=REPERES)
        self.assertIsNotNone(
            avec['vue_interne']['scenario_butane_non_subventionne'])
        self.assertIsNotNone(avec['vue_interne']['van_mad'])
