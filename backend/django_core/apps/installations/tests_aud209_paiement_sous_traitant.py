"""AUD209 — le règlement sous-traitant passe enfin par la chaîne AP standard.

Défaut d'origine (audit L3 ERP, round R2) : ``POST
/api/django/installations/paiements-sous-traitant/`` — le SEUL endpoint de
règlement des sous-traitants — appelait ``stock.services
.add_paiement_sous_traitant`` et s'arrêtait là :

  * aucune RAS-TVA (XPUR2) n'était calculée ni prélevée, alors que le chemin
    fournisseur générique (``stock.views.paiement_fournisseur.perform_create``)
    la calcule côté serveur depuis la LF 2024 ;
  * les gates XPUR4 (fournisseur bloqué pour les paiements) et XPUR1
    (document de conformité obligatoire manquant/expiré) étaient contournés ;
  * aucun ``paiement_fournisseur_enregistre`` n'était émis, donc AUCUNE
    écriture comptable n'était postée (YLEDG2).

Tests ROUGES avant le correctif (les quatre premiers) : un sous-traitant
assujetti à la RAS-TVA était réglé sans retenue et sans écriture, et les deux
gates ne bronchaient pas.

Non-régression explicite : l'appelant INTERNE
``compta.services.valider_compensation`` (compensation AR/AP, qui poste sa
propre écriture) reste HORS de cette chaîne — il appelle le service stock
directement, donc sans RAS et sans événement.

Run :
    python manage.py test apps.installations.tests_aud209_paiement_sous_traitant -v 2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta.models import EcritureComptable
from apps.stock.models import (
    AchatsParametres, DocumentConformiteFournisseur, FactureFournisseur,
    Fournisseur, PaiementFournisseur,
)
from apps.stock.services import add_paiement_sous_traitant, create_sous_traitant

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'
PAIEMENTS_URL = f'{BASE}/paiements-sous-traitant/'
DATE_PAIEMENT = datetime.date(2026, 5, 12)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    return Company.objects.create(slug=f'aud209-co-{n}', nom=f'AUD209 Co {n}')


class Aud209Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username=f'aud209-admin-{next(_seq)}', password='x',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.sous_traitant = create_sous_traitant(
            company=self.company, nom='Terrasol AUD209', metier='terrassement')
        # Facture sous-traitant 1 000 HT + 200 TVA = 1 200 TTC.
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AUD209-0001',
            fournisseur=self.sous_traitant, date_facture=DATE_PAIEMENT,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))

    def _activer_ras(self):
        AchatsParametres.objects.update_or_create(
            company=self.company, defaults={'ras_tva_actif': True})

    def _payer(self, montant='1200', **extra):
        payload = {'facture': self.facture.id, 'montant': montant,
                   'date_paiement': DATE_PAIEMENT.isoformat(),
                   'mode': 'virement'}
        payload.update(extra)
        return self.api.post(PAIEMENTS_URL, payload, format='json')


class TestRasTvaPrelevee(Aud209Base):
    """XPUR2 — la retenue à la source est calculée côté serveur."""

    def test_ras_tva_prelevee_sur_reglement_sous_traitant(self):
        self._activer_ras()

        resp = self._payer()

        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = PaiementFournisseur.objects.get(id=resp.data['id'])
        # Aucun ARF valide → retenue de 100 % de la part de TVA réglée.
        self.assertEqual(paiement.taux_ras, Decimal('100.00'))
        self.assertEqual(paiement.montant_ras_tva, Decimal('200.00'))

    def test_ras_tva_nulle_quand_parametre_off(self):
        # Défaut société : RAS-TVA inactive → comportement historique.
        resp = self._payer()

        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = PaiementFournisseur.objects.get(id=resp.data['id'])
        self.assertEqual(paiement.taux_ras, Decimal('0.00'))
        self.assertEqual(paiement.montant_ras_tva, Decimal('0.00'))


class TestEcriturePostee(Aud209Base):
    """YLEDG2 — l'événement documentaire fait poster l'écriture comptable."""

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_ecriture_postee_une_seule_fois(self):
        resp = self._payer(montant='600')

        self.assertEqual(resp.status_code, 201, resp.data)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement_fournisseur',
            source_id=resp.data['id'])
        self.assertEqual(qs.count(), 1)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_deux_reglements_deux_ecritures(self):
        premier = self._payer(montant='600')
        second = self._payer(montant='600')

        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(EcritureComptable.objects.filter(
            company=self.company,
            source_type='paiement_fournisseur').count(), 2)

    def test_aucune_ecriture_quand_toggle_off(self):
        resp = self._payer()

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(EcritureComptable.objects.filter(
            company=self.company).count(), 0)


class TestGatesXpur(Aud209Base):
    """XPUR4 + XPUR1 — les deux gates de paiement s'appliquent enfin ici."""

    def test_sous_traitant_bloque_paiements_refuse(self):
        self.sous_traitant.statut = Fournisseur.Statut.BLOQUE_PAIEMENTS
        self.sous_traitant.save(update_fields=['statut'])

        resp = self._payer()

        self.assertEqual(resp.status_code, 400)
        self.assertIn("Impossible d'enregistrer un paiement", str(resp.data))
        self.assertFalse(PaiementFournisseur.objects.filter(
            facture=self.facture).exists())

    def test_conformite_expiree_refuse_quand_blocage_actif(self):
        AchatsParametres.objects.update_or_create(
            company=self.company,
            defaults={'bloquer_paiement_conformite_expiree': True})
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.sous_traitant,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=DATE_PAIEMENT - datetime.timedelta(days=400),
            obligatoire=True)

        resp = self._payer()

        self.assertEqual(resp.status_code, 400)
        self.assertIn('Paiement bloqué', str(resp.data))
        self.assertFalse(PaiementFournisseur.objects.filter(
            facture=self.facture).exists())

    def test_conformite_expiree_toleree_quand_blocage_off(self):
        # Paramètre société OFF (défaut) → comportement historique préservé.
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.sous_traitant,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=DATE_PAIEMENT - datetime.timedelta(days=400),
            obligatoire=True)

        resp = self._payer()

        self.assertEqual(resp.status_code, 201, resp.data)


class TestAppelantInterneCompta(Aud209Base):
    """L'appelant interne (compensation AR/AP) reste HORS de la chaîne."""

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_service_direct_sans_ras_ni_ecriture(self):
        self._activer_ras()

        paiement = add_paiement_sous_traitant(
            company=self.company, user=self.admin, facture=self.facture,
            montant=Decimal('1200'), date_paiement=DATE_PAIEMENT,
            mode='autre', note='Compensation AR/AP TEST')

        self.assertEqual(paiement.taux_ras, Decimal('0.00'))
        self.assertEqual(paiement.montant_ras_tva, Decimal('0.00'))
        self.assertEqual(EcritureComptable.objects.filter(
            company=self.company, source_type='paiement_fournisseur',
            source_id=paiement.id).count(), 0)
