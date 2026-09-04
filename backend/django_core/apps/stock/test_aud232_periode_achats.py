"""AUD232 — garde de période comptable EN AMONT des documents d'achat.

Défaut d'origine : le refus d'un document daté dans une période CLÔTURÉE
n'existait qu'au fond de la pile (``EcritureComptable.save``, FG115) et
seulement quand ``COMPTA_AUTO_ECRITURES`` est actif (défaut OFF). Résultat :
  * toggle OFF — facture/paiement fournisseur ANTIDATÉ dans un mois clos
    accepté sans que rien ne bronche ;
  * toggle ON — ``ValidationError`` non traduite levée APRÈS la création de la
    facture (le ``send`` de `perform_create` vivait HORS de toute transaction,
    ``ATOMIC_REQUESTS`` étant absent des settings) → facture orpheline.

La garde est désormais posée sur le DOCUMENT, comme sur les 26 autres sites du
même patron, et la création + l'événement partagent une transaction.

Run :
    python manage.py test apps.stock.test_aud232_periode_achats -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta.models import PeriodeComptable
from apps.stock.models import FactureFournisseur, Fournisseur
from apps.stock.services import add_paiement_sous_traitant

User = get_user_model()

FERMEE = datetime.date(2026, 2, 10)     # dans la période verrouillée
OUVERTE = datetime.date(2026, 5, 12)    # hors période verrouillée


def make_company(slug='aud232-co', nom='AUD232 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud232Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud232_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Sous-traitant AUD232', type='service')
        PeriodeComptable.objects.create(
            company=self.company, date_debut=datetime.date(2026, 2, 1),
            date_fin=datetime.date(2026, 2, 28), verrouillee=True)

    def _facture(self, date_facture=OUVERTE, montant='1000'):
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-AUD232-{date_facture}',
            fournisseur=self.fournisseur, date_facture=date_facture,
            montant_ttc=Decimal(montant))


class TestFactureFournisseur(Aud232Base):
    def test_facture_antidatee_en_periode_close_refusee(self):
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_facture': FERMEE.isoformat(),
            'montant_ttc': '5000',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('Période comptable clôturée', str(resp.data))
        # Aucun document orphelin n'a été créé.
        self.assertFalse(FactureFournisseur.objects.filter(
            company=self.company, date_facture=FERMEE).exists())

    def test_facture_en_periode_ouverte_acceptee(self):
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_facture': OUVERTE.isoformat(),
            'montant_ttc': '5000',
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(FactureFournisseur.objects.filter(
            company=self.company, date_facture=OUVERTE).exists())


class TestPaiementFournisseur(Aud232Base):
    def test_paiement_date_en_periode_close_refuse(self):
        facture = self._facture()

        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '100',
            'date_paiement': FERMEE.isoformat(), 'mode': 'virement',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('Période comptable clôturée', str(resp.data))
        self.assertEqual(facture.paiements.count(), 0)

    def test_paiement_en_periode_ouverte_accepte(self):
        facture = self._facture()

        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '100',
            'date_paiement': OUVERTE.isoformat(), 'mode': 'virement',
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(facture.paiements.count(), 1)

    def test_action_paiements_de_la_facture_refuse_aussi(self):
        facture = self._facture()

        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '100', 'date_paiement': FERMEE.isoformat(),
             'mode': 'virement'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('Période comptable clôturée', str(resp.data))
        self.assertEqual(facture.paiements.count(), 0)


class TestPaiementSousTraitant(Aud232Base):
    def test_service_refuse_une_date_en_periode_close(self):
        facture = self._facture()

        with self.assertRaises(ValueError) as ctx:
            add_paiement_sous_traitant(
                company=self.company, user=self.admin, facture=facture,
                montant=Decimal('100'), date_paiement=FERMEE)

        self.assertIn('Période comptable clôturée', str(ctx.exception))
        self.assertEqual(facture.paiements.count(), 0)

    def test_service_accepte_une_date_ouverte(self):
        facture = self._facture()

        add_paiement_sous_traitant(
            company=self.company, user=self.admin, facture=facture,
            montant=Decimal('100'), date_paiement=OUVERTE)

        self.assertEqual(facture.paiements.count(), 1)


class TestSansPeriodeVerrouillee(TestCase):
    """Sans période verrouillée (le cas de toutes les sociétés) : no-op."""

    def setUp(self):
        self.company = make_company('aud232-libre', 'AUD232 Libre')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur libre')

    def test_toute_date_est_acceptee(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AUD232-LIBRE',
            fournisseur=self.fournisseur, date_facture=FERMEE,
            montant_ttc=Decimal('1000'))

        add_paiement_sous_traitant(
            company=self.company, user=None, facture=facture,
            montant=Decimal('50'), date_paiement=FERMEE)

        self.assertEqual(facture.paiements.count(), 1)
