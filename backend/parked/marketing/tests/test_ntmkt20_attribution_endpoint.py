"""NTMKT20 — Endpoint de comparaison des modèles d'attribution
(``GET /api/django/marketing/attribution/comparaison/?devis_id=``).

Couvre : devis_id requis, les 4 modèles renvoyés pour un devis signé, le
modèle société configuré change ``modele_actuel``, 404 propre (non accepté /
autre société) — jamais une fuite d'existence cross-tenant.
"""
from decimal import Decimal

from django.utils import timezone

from apps.crm.models import Lead, PointContact
from apps.marketing import services as mkt_services

from testkit.base import TenantAPITestCase
from testkit.factories import DevisFactory, LigneDevisFactory


class AttributionComparaisonEndpointTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(company=self.company, nom='Lead A')
        self.devis = DevisFactory(
            company=self.company, lead=self.lead, statut='accepte')
        LigneDevisFactory(
            devis=self.devis, quantite=Decimal('1'),
            prix_unitaire=Decimal('500.00'), remise=Decimal('0'))
        PointContact.objects.create(
            company=self.company, lead=self.lead, canal='meta_ads',
            date_contact=timezone.now(), ordre=1)

    def test_endpoint_exige_devis_id(self):
        res = self.client_as().get(
            '/api/django/marketing/attribution/comparaison/')
        self.assertEqual(res.status_code, 400)

    def test_endpoint_devis_signe_renvoie_les_4_modeles(self):
        res = self.client_as().get(
            '/api/django/marketing/attribution/comparaison/',
            {'devis_id': self.devis.id})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(
            set(data['modeles']),
            {'dernier_touche', 'premier_touche', 'lineaire',
             'pondere_temporel'})
        # Défaut = dernier-touche = comportement XMKT17 actuel inchangé.
        self.assertEqual(data['modele_actuel'], 'dernier_touche')

    def test_endpoint_devis_non_accepte_404(self):
        self.devis.statut = 'brouillon'
        self.devis.save(update_fields=['statut'])
        res = self.client_as().get(
            '/api/django/marketing/attribution/comparaison/',
            {'devis_id': self.devis.id})
        self.assertEqual(res.status_code, 404)

    def test_endpoint_devis_autre_societe_404(self):
        devis_autre = DevisFactory(
            company=self.other_company, lead=None, statut='accepte')
        res = self.client_as().get(
            '/api/django/marketing/attribution/comparaison/',
            {'devis_id': devis_autre.id})
        self.assertEqual(res.status_code, 404)

    def test_modele_societe_configure_change_le_modele_actuel_affiche(self):
        parametres = mkt_services.parametres_marketing_pour(self.company)
        parametres.modele_attribution = 'lineaire'
        parametres.save(update_fields=['modele_attribution'])
        res = self.client_as().get(
            '/api/django/marketing/attribution/comparaison/',
            {'devis_id': self.devis.id})
        self.assertEqual(res.json()['modele_actuel'], 'lineaire')
