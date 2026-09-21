"""Tests NTCON7 — Avenant marché côté projet (chiffrage + approbation).

Couvre :
* création (référence race-safe, préfixe AVC) ;
* approbation ``impact_budget=False`` → génère une facture d'acompte
  (``ventes.services.creer_facture_acompte_situation``) ;
* approbation ``impact_budget=True`` → référence lâche ``budget_projet_id``
  (best-effort), AUCUNE facture générée ;
* refus n'impacte jamais rien (ni facture, ni budget) ;
* décision déjà prise → 400 (idempotence de la state machine) ;
* cross-tenant refusé.
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import AvenantChantier

from .helpers import auth, make_chantier, make_client_crm, make_company, make_user

BASE = '/api/django/btp-chantier/avenants-chantier/'


class AvenantChantierApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.client_crm = make_client_crm(self.co)
        self.chantier = make_chantier(self.co, client=self.client_crm)

    def test_create_avenant_reference_prefix(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'description': 'Ajout climatisation',
            'montant_ht': '15000.00',
            'impact_delai_jours': 5,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['reference'].startswith('AVC-'))
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_approuver_facture_acompte(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-TEST-0001', description='Test',
            montant_ht='10000.00', impact_budget=False)
        api = auth(self.user)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve')
        self.assertIsNotNone(resp.data['facture_id'])
        self.assertIsNone(resp.data['budget_projet_id'])

        from apps.ventes.models import Facture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        self.assertEqual(facture.type_facture, Facture.TypeFacture.ACOMPTE)
        self.assertEqual(str(facture.client_id), str(self.client_crm.id))

    def test_approuver_impact_budget_sans_facture(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-TEST-0002', description='Test budget',
            montant_ht='5000.00', impact_budget=True)
        api = auth(self.user)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve')
        self.assertIsNone(resp.data['facture_id'])
        # Aucun projet rattaché dans ce test -> best-effort renvoie None,
        # n'empêche jamais l'approbation.
        self.assertIsNone(resp.data['budget_projet_id'])

        from apps.ventes.models import Facture
        self.assertEqual(Facture.objects.count(), 0)

    def test_refuser_n_impacte_rien(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-TEST-0003', description='Test refus',
            montant_ht='2000.00')
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{avenant.id}/refuser/', {'motif': 'Trop cher'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'refuse')
        self.assertIsNone(resp.data['facture_id'])
        self.assertIsNone(resp.data['budget_projet_id'])
        from apps.ventes.models import Facture
        self.assertEqual(Facture.objects.count(), 0)

    def test_approuver_deux_fois_refuse(self):
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-TEST-0004', description='Test',
            montant_ht='1000.00', statut=AvenantChantier.Statut.APPROUVE)
        api = auth(self.user)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approuver_sans_client_refuse(self):
        chantier_sans_client = make_chantier(self.co)
        avenant = AvenantChantier.objects.create(
            company=self.co, chantier=chantier_sans_client,
            reference='AVC-TEST-0005', description='Test',
            montant_ht='1000.00', impact_budget=False)
        api = auth(self.user)
        resp = api.post(f'{BASE}{avenant.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_avenant = AvenantChantier.objects.create(
            company=other_co, chantier=other_chantier,
            reference='AVC-OTHER-0001', description='Autre',
            montant_ht='1000.00')
        api = auth(self.user)
        resp = api.get(f'{BASE}{other_avenant.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
