"""Copilote — devis AUTOMATIQUE (résidentiel) + garde-fou « toujours auto ».

``build_devis_auto()`` dimensionne un devis résidentiel depuis la fiche lead
(facture d'hiver ou taille souhaitée) et délègue à ``build_devis_from_layout``.
L'agent n'a plus d'action de création VIDE : seule ``ventes.devis.creer_auto``
subsiste, avec les actions d'édition par chat.

Run:
    python manage.py test apps.ventes.tests.test_devis_auto -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_auto, AutoDevisError

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def seed_catalogue(company):
    """Catalogue minimal (mêmes désignations que seed_catalogue)."""
    def mk(nom, sku, prix):
        Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Deyness 5 kWh', f'BAT-{company.pk}', 17000)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


AUTO_URL = '/api/django/ventes/devis/auto/'


class BuildDevisAutoServiceTest(TestCase):
    def setUp(self):
        self.company = make_company('auto-co')
        self.user = User.objects.create_user(
            username='autouser', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='Lead',
            email='auto@ex.com', **extra)

    def test_sizes_from_facture_hiver(self):
        # 1800 / 900 = 2 tranches × 8 = 16 panneaux ; 16×710/1000 = 11.36 kWc.
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800')),
            user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 16)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('réseau' in d for d in desigs))
        self.assertFalse(any('Batterie' in d for d in desigs))
        self.assertAlmostEqual(
            float(devis.etude_params['puissance_kwc']), 11.36, places=2)

    def test_sizes_from_taille_souhaitee(self):
        # 6 kWc → round(6000 / 710) = 8 panneaux.
        devis = build_devis_auto(
            lead=self._lead(taille_souhaitee_kwc=Decimal('6')),
            user=self.user, company=self.company)
        panel = next(li for li in devis.lignes.all()
                     if 'Panneau' in li.designation)
        self.assertEqual(int(panel.quantite), 8)

    def test_battery_added_when_wanted(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('1800'),
                            batterie_souhaitee='avec'),
            user=self.user, company=self.company)
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('hybride' in d for d in desigs))
        self.assertTrue(any('Batterie' in d for d in desigs))
        self.assertFalse(any('réseau' in d for d in desigs))

    def test_missing_data_raises(self):
        with self.assertRaises(AutoDevisError):
            build_devis_auto(lead=self._lead(), user=self.user,
                             company=self.company)

    def test_low_bill_raises(self):
        with self.assertRaises(AutoDevisError):
            build_devis_auto(lead=self._lead(facture_hiver=Decimal('500')),
                             user=self.user, company=self.company)

    def test_non_residential_raises(self):
        for marche in ('agricole', 'industriel', 'commercial'):
            with self.assertRaises(AutoDevisError):
                build_devis_auto(
                    lead=self._lead(facture_hiver=Decimal('1800'),
                                    type_installation=marche),
                    user=self.user, company=self.company)

    def test_blank_market_treated_residential(self):
        devis = build_devis_auto(
            lead=self._lead(facture_hiver=Decimal('900')),
            user=self.user, company=self.company)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


class AutoEndpointTest(TestCase):
    def setUp(self):
        self.company = make_company('autoep-co')
        self.user = User.objects.create_user(
            username='autoep', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def test_creates_dimensioned_devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ep', prenom='Lead',
            facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')
        self.assertGreater(resp.data['nb_lignes'], 0)
        self.assertTrue(resp.data['reference'].startswith('DEV-'))

    def test_cross_tenant_lead_404(self):
        other = make_company('autoep-other')
        other_lead = Lead.objects.create(
            company=other, nom='Foreign', facture_hiver=Decimal('1800'))
        resp = self.api.post(AUTO_URL, {'lead': other_lead.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)

    def test_non_residential_422(self):
        lead = Lead.objects.create(
            company=self.company, nom='Agri', facture_hiver=Decimal('1800'),
            type_installation='agricole')
        resp = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertEqual(resp.data.get('field'), 'type_installation')

    def test_requires_auth(self):
        lead = Lead.objects.create(
            company=self.company, nom='NoAuth', facture_hiver=Decimal('1800'))
        resp = APIClient().post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertIn(resp.status_code, (401, 403))


class GuardrailTest(TestCase):
    """Le Copilote ne peut PLUS créer un devis vide : seules l'auto-création et
    l'édition par chat subsistent au catalogue."""

    def test_empty_create_actions_gone_auto_present(self):
        from apps.agent.registry import all_actions
        keys = {a.key for a in all_actions()}
        self.assertNotIn('ventes.devis.create', keys)
        self.assertNotIn('ventes.devis.creer', keys)
        self.assertIn('ventes.devis.creer_auto', keys)

    def test_edit_actions_present_with_expected_risk(self):
        from apps.ventes.agent_actions import (
            LIGNE_AJOUTER, LIGNE_MODIFIER, LIGNE_SUPPRIMER, REMISE_DEVIS,
        )
        from apps.agent.registry import RISK_INTERNAL, RISK_OUTWARD
        self.assertEqual(LIGNE_AJOUTER.risk, RISK_INTERNAL)
        self.assertEqual(LIGNE_MODIFIER.risk, RISK_INTERNAL)
        self.assertEqual(REMISE_DEVIS.risk, RISK_INTERNAL)
        # Suppression → confirmation (outward).
        self.assertEqual(LIGNE_SUPPRIMER.risk, RISK_OUTWARD)
        self.assertTrue(LIGNE_SUPPRIMER.confirm_summary)

    def test_creer_auto_inputs_have_no_company(self):
        from apps.ventes.agent_actions import CREER_AUTO
        self.assertNotIn('company', CREER_AUTO.inputs.get('properties', {}))
