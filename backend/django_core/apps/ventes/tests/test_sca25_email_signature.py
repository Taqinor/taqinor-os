"""SCA25 — les 5 corps d'email transactionnels signent avec la marque de la
SOCIÉTÉ (BrandedTemplate ou repli « L'équipe {nom} »), jamais « TAQINOR » codé
en dur.

On appelle directement les fonctions d'``email_service`` (backend locmem →
aucun envoi réseau) et on inspecte le corps consigné dans ``EmailLog.corps``.
Un tenant sans modèle reçoit SON propre nom ; le fondateur (société nommée
« TAQINOR ») conserve « L'équipe TAQINOR » — comportement préservé PAR LA
DONNÉE (``CompanyProfile.nom``), pas par le code.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes import email_service
from apps.ventes.models import Devis, EmailLog, Facture, Paiement
from core.models import BrandedTemplate
from core.selectors import EMAIL_SIGNATURE_CODE

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_client(company, email='sca25@example.com'):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Sara',
        email=email, telephone='+212600000099', adresse='Rabat')


def make_facture(company, client, user, ref='FAC'):
    return Facture.objects.create(
        company=company, reference=f'{ref}-{MONTH}-9001', client=client,
        statut=Facture.Statut.EMISE, montant_ht=Decimal('4166.67'),
        montant_tva=Decimal('833.33'), montant_ttc=Decimal('5000'),
        created_by=user)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SCA25TenantSignatureTests(TestCase):
    """Un tenant NON-TAQINOR : sa signature porte SON nom, jamais TAQINOR."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('sca25-acme', 'ACME Énergie')
        cls.user = User.objects.create_user(
            username='sca25_acme', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_obj = make_client(cls.company)

    def _assert_own_name_no_taqinor(self, log):
        self.assertIsNotNone(log)
        self.assertIn("L'équipe ACME Énergie", log.corps)
        self.assertNotIn('TAQINOR', log.corps)

    def test_document_email_body_signature(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-SCA25-1',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        email_service.send_document_email(devis, user=self.user)
        self._assert_own_name_no_taqinor(
            EmailLog.objects.filter(devis=devis).first())

    def test_relance_email_body_signature(self):
        fac = make_facture(self.company, self.client_obj, self.user, 'FACR')
        email_service.send_relance_email(fac, user=self.user)
        self._assert_own_name_no_taqinor(
            EmailLog.objects.filter(facture=fac).first())

    def test_pre_echeance_email_body_signature(self):
        fac = make_facture(self.company, self.client_obj, self.user, 'FACP')
        email_service.send_pre_echeance_email(fac, user=self.user)
        self._assert_own_name_no_taqinor(
            EmailLog.objects.filter(facture=fac).first())

    def test_recu_email_body_signature(self):
        fac = make_facture(self.company, self.client_obj, self.user, 'FACQ')
        paiement = Paiement.objects.create(
            company=self.company, facture=fac, montant=Decimal('2000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.user)
        email_service.send_recu_email(paiement, user=self.user)
        self._assert_own_name_no_taqinor(
            EmailLog.objects.filter(facture=fac).last())

    def test_releve_email_body_signature(self):
        email_service.send_releve_email(self.client_obj, {}, user=self.user)
        self._assert_own_name_no_taqinor(
            EmailLog.objects.filter(client=self.client_obj).last())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SCA25FounderPreservedTests(TestCase):
    """Société nommée « TAQINOR » → « L'équipe TAQINOR » (par la donnée)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('sca25-taqinor', 'TAQINOR')
        cls.user = User.objects.create_user(
            username='sca25_taqinor', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_obj = make_client(cls.company, 'founder@example.com')

    def test_founder_signature_still_taqinor(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-SCA25-TAQ',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        email_service.send_document_email(devis, user=self.user)
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertIn("L'équipe TAQINOR", log.corps)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SCA25BrandedTemplateTests(TestCase):
    """Un BrandedTemplate email/signature actif pilote la signature du corps."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('sca25-tpl', 'Helios SARL')
        cls.user = User.objects.create_user(
            username='sca25_tpl', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_obj = make_client(cls.company, 'tpl@example.com')
        BrandedTemplate.objects.create(
            company=cls.company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Signature',
            corps='Sincèrement,\nLe service client {{ nom }}')

    def test_template_body_used(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-SCA25-TPL',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        email_service.send_document_email(devis, user=self.user)
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertIn('Le service client Helios SARL', log.corps)
        self.assertNotIn("L'équipe", log.corps)
