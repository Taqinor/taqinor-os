"""QJR545 (Groupe QJR5, contrat QJR503 ``devis_verrou_edition.json``) — verrou
OPTIMISTE serveur : 409 ``devis_modifie`` si le devis ou ses lignes ont bougé
depuis l'ouverture (resynchro catalogue comprise) ; jeton absent ⇒ inchangé ;
toute réponse 2xx porte ``updated_at``.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'devis_verrou_edition.json')


class TestDevisVerrouEdition(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.company = Company.objects.create(
            nom='QJR545 Co', slug='qjr545-co')
        cls.user_a = User.objects.create_user(
            username='qjr545_a', password='x', role_legacy='responsable',
            company=cls.company, first_name='Sami', last_name='Alaoui')
        cls.user_b = User.objects.create_user(
            username='qjr545_b', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR545',
            email='qjr545@example.com', telephone='+212600005450')
        cls.panneau = Produit.objects.create(
            company=cls.company, nom='Panneau Canadien Solar 710W',
            sku='QJR545-PV', prix_vente=Decimal('1450'), quantite_stock=100)
        cls.onduleur = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau Huawei 5kW Monophasé',
            sku='QJR545-OND', prix_vente=Decimal('9000'), quantite_stock=10)

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _devis(self, num, company=None, client=None):
        devis = Devis.objects.create(
            company=company or self.company,
            reference=f'DEV-{MONTH}-{5450 + num * 10}',
            client=client or self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('8'), prix_unitaire=Decimal('1450'),
            remise=Decimal('0'))
        return devis

    def _lignes(self, qte):
        return [
            {'produit': self.panneau.id, 'designation': self.panneau.nom,
             'quantite': str(qte), 'prix_unitaire': '1450.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 0},
            {'produit': self.onduleur.id, 'designation': self.onduleur.nom,
             'quantite': '1', 'prix_unitaire': '9000.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 1},
        ]

    def _jeton(self, api, devis):
        r = api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data['updated_at']

    def _replace(self, api, devis, corps):
        return api.post(f'/api/django/ventes/devis/{devis.id}/replace-lines/',
                        corps, format='json')

    def test_contrat_409_forme(self):
        self.assertEqual(self.contrat['exemple_409']['code'], 'devis_modifie')
        self.assertIn('expected_updated_at', self.contrat['corps'])

    def test_a_deux_ouvertures_b_ecrase_refuse(self):
        devis = self._devis(1)
        api_a, api_b = self._api(self.user_a), self._api(self.user_b)
        jeton_a, jeton_b = self._jeton(api_a, devis), self._jeton(api_b, devis)
        r = self._replace(api_a, devis, {'lignes': self._lignes(10),
                                         'expected_updated_at': jeton_a})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('updated_at', r.data)
        r = self._replace(api_b, devis, {'lignes': self._lignes(4),
                                         'expected_updated_at': jeton_b})
        self.assertEqual(r.status_code, 409, r.content)
        corps = r.json()
        self.assertEqual(set(corps), set(self.contrat['exemple_409']))
        self.assertEqual(corps['code'], 'devis_modifie')
        panneaux = devis.lignes.get(produit=self.panneau)
        self.assertEqual(panneaux.quantite, Decimal('10'))

    def test_b_resynchro_catalogue_entre_ouverture_et_sauvegarde(self):
        devis = self._devis(2)
        api = self._api(self.user_a)
        jeton = self._jeton(api, devis)
        from apps.ventes.domain.catalogue_events import (
            resynchroniser_devis_pour_produit)
        # ASTK140 — l'événement suit l'écriture du produit (catalogue à 1500).
        Produit.objects.filter(pk=self.panneau.pk).update(
            prix_vente=Decimal('1500'))
        resultat = resynchroniser_devis_pour_produit(
            produit=self.panneau, company=self.company,
            champs={'prix_vente': ['1450', '1500']})
        self.assertEqual(resultat['devis_touches'], 1)
        r = self._replace(api, devis, {'lignes': self._lignes(9),
                                       'expected_updated_at': jeton})
        self.assertEqual(r.status_code, 409, r.content)

    def test_c_jeton_de_la_reponse_precedente_passe(self):
        devis = self._devis(3)
        api = self._api(self.user_a)
        jeton = self._jeton(api, devis)
        r = self._replace(api, devis, {
            'lignes': self._lignes(10), 'entete': {'note': 'un'},
            'expected_updated_at': jeton})
        self.assertEqual(r.status_code, 200, r.content)
        r = self._replace(api, devis, {
            'lignes': self._lignes(11), 'entete': {'note': 'deux'},
            'expected_updated_at': r.data['updated_at']})
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.note, 'deux')

    def test_d_sans_jeton_inchange(self):
        devis = self._devis(4)
        api = self._api(self.user_a)
        self._replace(api, devis, {'lignes': self._lignes(10)})
        r = self._replace(api, devis, {'lignes': self._lignes(12)})
        self.assertEqual(r.status_code, 200, r.content)

    def test_e_autre_societe_404(self):
        autre = Company.objects.create(nom='QJR545 Autre', slug='qjr545-autre')
        client_autre = Client.objects.create(
            company=autre, nom='Autre', email='autre545@example.com')
        devis = self._devis(5, company=autre, client=client_autre)
        r = self._replace(self._api(self.user_a), devis, {
            'lignes': self._lignes(10),
            'expected_updated_at': timezone.now().isoformat()})
        self.assertEqual(r.status_code, 404, r.content)

    def test_patch_entete_jeton_perime_409(self):
        devis = self._devis(6)
        api = self._api(self.user_a)
        jeton = self._jeton(api, devis)
        Devis.objects.filter(pk=devis.pk).update(
            updated_at=timezone.now(), updated_by=self.user_a)
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                      {'note': 'x', 'expected_updated_at': jeton},
                      format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json()['updated_by_nom'], 'Sami Alaoui')

    def test_etude_params_porte_updated_at_et_ignore_le_jeton(self):
        devis = self._devis(7)
        api = self._api(self.user_a)
        jeton = self._jeton(api, devis)
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/etude-params/',
                      {'scenario': 'Sans batterie',
                       'expected_updated_at': jeton}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('expected_updated_at', r.data['etude_params'])
        from django.utils.dateparse import parse_datetime
        self.assertEqual(parse_datetime(r.data['updated_at']),
                         parse_datetime(self._jeton(api, devis)))
