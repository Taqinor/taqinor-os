"""
XFAC28 — Blocage crédit dur configurable avec déblocage autorisé (étend FG41).

Hold ON + client en dépassement -> accepter refusé avec message chiffré ;
l'override responsable passe et laisse une trace ; hold OFF -> strictement
le warning FG41 actuel.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac28_credit_hold -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, Facture, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac28-co', nom='XFAC28 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC28CreditHoldTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xfac28_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hold', prenom='Client',
            email='xfac28@example.com', telephone='+212600000069',
            adresse='Casablanca', plafond_credit=Decimal('1000'),
        )
        # Encours existant qui dépasse déjà le plafond (1000 MAD).
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-5001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('2000'), created_by=self.admin,
        )
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='SKU-XFAC28',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10,
        )
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-5001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.admin,
        )
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
        )

    def _activate_hold(self):
        profile = CompanyProfile.get(company=self.company)
        profile.credit_hold_actif = True
        profile.save(update_fields=['credit_hold_actif'])

    def test_hold_off_accepter_passes_warning_only(self):
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/accepter/',
            {'nom': 'Client Test'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)

    def test_hold_on_client_over_limit_accepter_refused(self):
        self._activate_hold()
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/accepter/',
            {'nom': 'Client Test'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(r.data.get('credit_hold'))
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_hold_on_override_passes_and_is_audited(self):
        self._activate_hold()
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/accepter/',
            {'nom': 'Client Test', 'override_credit': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(DevisActivity.objects.filter(
            devis=self.devis, field='credit_hold').exists())

    def test_hold_on_client_under_limit_not_blocked(self):
        self._activate_hold()
        other_client = Client.objects.create(
            company=self.company, nom='OK', email='xfac28b@example.com',
            plafond_credit=Decimal('100000'),
        )
        devis2 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-5002',
            client=other_client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.admin,
        )
        LigneDevis.objects.create(
            devis=devis2, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
        )
        r = self.api.post(
            f'/api/django/ventes/devis/{devis2.id}/accepter/',
            {'nom': 'Client OK'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
