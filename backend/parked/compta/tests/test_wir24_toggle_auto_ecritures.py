"""Tests WIR24 — l'auto-génération des écritures comptables est réglable PAR
SOCIÉTÉ (``parametres.CompanyProfile.comptabilite_auto_ecritures``), en plus du
réglage global ``COMPTA_AUTO_ECRITURES``, et le détail d'une facture pointe vers
l'écriture GL générée (``GET /compta/ecritures/?source_type=&source_id=``).

Le réglage global reste un interrupteur maître (couvert par les tests YLEDG1) ;
ici on vérifie que, GLOBAL OFF (défaut), le drapeau société active — ou non —
l'écriture, et que l'écriture n'est visible/pointée que pour sa propre société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services
from apps.compta.models import EcritureComptable
from apps.crm.models import Client
from apps.parametres.models_company import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
from core.events import facture_emise

from apps.compta import receivers  # noqa: F401  (câblage ready())

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_facture(company, ref):
    cl = Client.objects.create(
        company=company, nom='Client', prenom='WIR24',
        email=f'{ref}@example.com', telephone='+212600000024')
    produit = Produit.objects.create(
        company=company, nom='Panneau', sku=f'PAN-{ref}',
        prix_vente=Decimal('1000'), quantite_stock=10, tva=Decimal('20.00'))
    facture = Facture.objects.create(
        company=company, reference=ref, client=cl,
        statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))
    LigneFacture.objects.create(
        facture=facture, produit=produit, designation='Panneau',
        quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
        taux_tva=Decimal('20.00'))
    return facture


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir24PerCompanyToggle(TestCase):
    def setUp(self):
        # Société A : toggle activé ; Société B : toggle laissé au défaut (OFF).
        self.co_a = make_company('wir24-a', 'WIR24 A')
        self.co_b = make_company('wir24-b', 'WIR24 B')
        profil = CompanyProfile.get(self.co_a)
        profil.comptabilite_auto_ecritures = True
        profil.save(update_fields=['comptabilite_auto_ecritures'])

    def test_service_toggle_par_societe(self):
        # GLOBAL OFF (défaut) : A actif via son drapeau, B inactif, None neutre.
        self.assertTrue(services.auto_ecritures_actif(self.co_a))
        self.assertFalse(services.auto_ecritures_actif(self.co_b))
        self.assertFalse(services.auto_ecritures_actif())

    def test_facture_emise_poste_ecriture_quand_toggle_actif(self):
        facture = make_facture(self.co_a, 'FAC-WIR24-A-0001')
        facture_emise.send(
            sender=Facture, instance=facture, company=self.co_a)
        qs = EcritureComptable.objects.filter(
            company=self.co_a, source_type='facture', source_id=facture.id)
        self.assertEqual(qs.count(), 1)
        # Idempotent : une ré-émission ne poste pas une seconde écriture.
        facture_emise.send(
            sender=Facture, instance=facture, company=self.co_a)
        self.assertEqual(qs.count(), 1)

    def test_facture_emise_noop_quand_toggle_societe_off(self):
        facture = make_facture(self.co_b, 'FAC-WIR24-B-0001')
        facture_emise.send(
            sender=Facture, instance=facture, company=self.co_b)
        self.assertEqual(
            EcritureComptable.objects.filter(company=self.co_b).count(), 0)

    def test_selector_ecriture_pour_source(self):
        facture = make_facture(self.co_a, 'FAC-WIR24-A-0002')
        facture_emise.send(
            sender=Facture, instance=facture, company=self.co_a)
        ecriture = selectors.ecriture_pour_source(
            self.co_a, 'facture', facture.id)
        self.assertIsNotNone(ecriture)
        self.assertEqual(ecriture.source_id, facture.id)
        # Company-scoped : B ne voit pas l'écriture de A.
        self.assertIsNone(
            selectors.ecriture_pour_source(self.co_b, 'facture', facture.id))

    def test_detail_facture_pointe_vers_ecriture_gl(self):
        facture = make_facture(self.co_a, 'FAC-WIR24-A-0003')
        facture_emise.send(
            sender=Facture, instance=facture, company=self.co_a)
        user = User.objects.create_user(
            username='wir24-a-user', password='x', company=self.co_a,
            role_legacy='responsable')
        resp = auth(user).get(
            '/api/django/compta/ecritures/',
            {'source_type': 'facture', 'source_id': facture.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        results = data['results'] if isinstance(data, dict) and 'results' in data \
            else data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_type'], 'facture')
        self.assertEqual(results[0]['source_id'], facture.id)
