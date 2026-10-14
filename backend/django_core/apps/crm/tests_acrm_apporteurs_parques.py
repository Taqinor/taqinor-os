"""ACRM66 (D-ACRM-6 (iii)=(b), 09/10/2026) — apporteurs et deals enregistrés
PARQUÉS derrière ``CompanyProfile.apporteurs_actif`` (éteint par défaut).

Éteint : ``apporteurs/``, ``deals-enregistres/`` et ``deals-enregistres/
a-payer/`` répondent 404 et le devis accepté ne calcule AUCUNE commission
(deal relu en base : inchangé). Allumé : commission posée, deal À_PAYER,
routes servies comme avant. Récepteur et signal réels, aucun mock.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.clients_identite import resolve_client_for_lead
from apps.crm.models import Apporteur, DealEnregistre, Lead
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from core.events import devis_accepted

User = get_user_model()
ROUTES = ('/api/django/crm/apporteurs/',
          '/api/django/crm/deals-enregistres/',
          '/api/django/crm/deals-enregistres/a-payer/')


class ApporteursParquesTests(TestCase):

    def _societe(self, slug, actif):
        company = Company.objects.create(nom=slug, slug=slug)
        CompanyProfile.objects.update_or_create(
            company=company, defaults={'apporteurs_actif': actif})
        apporteur = Apporteur.objects.create(
            company=company, nom=f'Apporteur {slug}',
            taux_commission_pct=Decimal('5.00'))
        lead = Lead.objects.create(company=company, nom=f'Lead {slug}')
        deal = DealEnregistre.objects.create(
            company=company, apporteur=apporteur, lead=lead,
            statut=DealEnregistre.Statut.APPROUVE)
        devis = Devis.objects.create(
            company=company, client=resolve_client_for_lead(lead), lead=lead,
            reference=f'DEV-{slug.upper()}-10', statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=devis, designation='Panneaux mono 550W', quantite=1,
            prix_unitaire=Decimal('10000.00'))
        user = User.objects.create_user(
            username=f'{slug}-resp', password='x', role_legacy='responsable',
            company=company)
        api = APIClient()
        api.force_authenticate(user)
        return deal, devis, api

    def test_eteint_aucune_commission(self):
        deal, devis, _api = self._societe('acrm66-off', actif=False)
        devis_accepted.send(
            sender='test', devis=devis, user=None, ancien_statut='envoye')
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.APPROUVE)
        self.assertIsNone(deal.montant_commission_du)

    def test_eteint_routes_404(self):
        _deal, _devis, api = self._societe('acrm66-off-routes', actif=False)
        for url in ROUTES:
            with self.subTest(url=url):
                self.assertEqual(api.get(url).status_code, 404)

    def test_methode_non_portee_405_meme_eteint(self):
        """CI #997 api-fuzz : TRACE n'est portée par aucune de ces routes — le
        schéma attend 405, la porte parquée ne répond pas 404 à sa place."""
        _deal, _devis, api = self._societe('acrm66-trace', actif=False)
        for url in ROUTES:
            with self.subTest(url=url):
                self.assertEqual(api.generic('TRACE', url).status_code, 405)
                self.assertEqual(api.get(url).status_code, 404)

    def test_allume_inchange(self):
        deal, devis, api = self._societe('acrm66-on', actif=True)
        devis_accepted.send(
            sender='test', devis=devis, user=None, ancien_statut='envoye')
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.A_PAYER)
        self.assertIsNotNone(deal.montant_commission_du)
        for url in ROUTES:
            with self.subTest(url=url):
                self.assertEqual(api.get(url).status_code, 200)
        a_payer = api.get(ROUTES[2]).json()
        self.assertEqual([d['id'] for d in a_payer], [deal.id])
