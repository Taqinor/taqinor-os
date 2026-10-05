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
from apps.ventes import selectors
from apps.ventes.domain import etude_schema as es
from apps.ventes.domain import pompage
from apps.ventes.models import Devis, LigneDevis
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
