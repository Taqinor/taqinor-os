"""ARC1 — Tests du socle multi-tenant ``core.models.TenantModel``.

Couverture :
  (a) ``TenantModel`` est une base ABSTRAITE (aucune table propre) et fournit
      ``company`` (FK ``authentication.Company``, CASCADE) + les timestamps
      ``created_at`` / ``updated_at`` (hérités de ``TimestampedModel``).
  (b) Le ``related_name`` par défaut ``'%(app_label)s_%(class)s_set'`` garantit
      des accesseurs inverses uniques par sous-classe concrète.
  (c) Les 3 modèles PILOTES convertis (``notifications.WhatsAppTemplate``,
      ``WhatsAppMessageLog``, ``Annonce``) héritent bien de ``TenantModel`` ET
      conservent leur accesseur inverse HISTORIQUE EXACT (jamais renommé) :
      ``company.whatsapp_bsp_templates`` / ``company.whatsapp_message_logs`` /
      ``company.annonces``.
  (d) Les pilotes portent toujours ``created_at`` / ``updated_at`` (via le
      socle) et une ``company`` obligatoire.

La règle de complétude de la conversion de masse reste YDATA2 (hors ARC1).
"""
from django.db import models
from django.test import TestCase

from authentication.models import Company

from apps.notifications.models import (
    Annonce,
    WhatsAppMessageLog,
    WhatsAppTemplate,
)
from core.models import TenantModel, TimestampedModel


class TenantModelAbstractTests(TestCase):
    """Contrat de la classe abstraite ``TenantModel`` (ARC1)."""

    def test_est_abstraite(self):
        """``TenantModel`` est abstraite : pas de table concrète."""
        self.assertTrue(TenantModel._meta.abstract)

    def test_herite_des_timestamps(self):
        """``TenantModel`` hérite de ``TimestampedModel`` (created/updated)."""
        self.assertTrue(issubclass(TenantModel, TimestampedModel))
        champs = {f.name for f in TenantModel._meta.get_fields()}
        self.assertIn('created_at', champs)
        self.assertIn('updated_at', champs)

    def test_fournit_company_fk_cascade(self):
        """``company`` est une FK obligatoire vers Company, en CASCADE."""
        company_field = TenantModel._meta.get_field('company')
        self.assertIsInstance(company_field, models.ForeignKey)
        # Sur le modèle ABSTRAIT, la référence paresseuse reste la chaîne
        # 'authentication.Company' ; elle se résout sur tout descendant
        # concret — on vérifie les deux.
        self.assertIn(
            company_field.remote_field.model,
            (Company, 'authentication.Company'))
        from apps.notifications.models import WhatsAppTemplate
        self.assertIs(
            WhatsAppTemplate._meta.get_field('company').remote_field.model,
            Company)
        self.assertEqual(
            company_field.remote_field.on_delete, models.CASCADE)
        # Obligatoire (multi-tenant) : non nullable.
        self.assertFalse(company_field.null)

    def test_related_name_par_defaut_parametrable(self):
        """Le related_name par défaut utilise le motif app_label/class."""
        company_field = TenantModel._meta.get_field('company')
        self.assertEqual(
            company_field.remote_field.related_name,
            '%(app_label)s_%(class)s_set')


class TenantModelPilotesTests(TestCase):
    """Les 3 pilotes convertis conservent leur socle ET leur accesseur (ARC1)."""

    PILOTES = [
        (WhatsAppTemplate, 'whatsapp_bsp_templates'),
        (WhatsAppMessageLog, 'whatsapp_message_logs'),
        (Annonce, 'annonces'),
    ]

    def test_pilotes_heritent_de_tenant_model(self):
        for model, _accessor in self.PILOTES:
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    issubclass(model, TenantModel),
                    f'{model.__name__} doit hériter de TenantModel')

    def test_pilotes_conservent_created_updated(self):
        for model, _accessor in self.PILOTES:
            with self.subTest(model=model.__name__):
                champs = {f.name for f in model._meta.get_fields()}
                self.assertIn('created_at', champs)
                self.assertIn('updated_at', champs)

    def test_pilotes_company_obligatoire_cascade(self):
        for model, _accessor in self.PILOTES:
            with self.subTest(model=model.__name__):
                cf = model._meta.get_field('company')
                self.assertEqual(cf.remote_field.model, Company)
                self.assertEqual(cf.remote_field.on_delete, models.CASCADE)

    def test_accesseur_inverse_historique_preserve(self):
        """L'accesseur inverse EXACT d'avant conversion est conservé.

        Un renommage (vers le motif par défaut) casserait le code appelant
        ``company.<related_name>`` — interdit par ARC1.
        """
        for model, accessor in self.PILOTES:
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    hasattr(Company, accessor),
                    f'Company.{accessor} doit exister (accesseur inverse '
                    f'historique de {model.__name__})')

    def test_accesseur_inverse_relie_le_bon_modele(self):
        """L'accesseur inverse pointe bien vers les instances du pilote."""
        company = Company.objects.create(nom='ARC1 Test SARL')

        tpl = WhatsAppTemplate.objects.create(
            company=company, name='devis_envoye_v1')
        log = WhatsAppMessageLog.objects.create(
            company=company, recipient='212600000000')
        annonce = Annonce.objects.create(company=company, titre='Bienvenue')

        self.assertIn(tpl, company.whatsapp_bsp_templates.all())
        self.assertIn(log, company.whatsapp_message_logs.all())
        self.assertIn(annonce, company.annonces.all())

    def test_timestamps_renseignes_a_la_creation(self):
        """created_at / updated_at (du socle) sont bien posés à la création."""
        company = Company.objects.create(nom='ARC1 Timestamps SARL')
        annonce = Annonce.objects.create(company=company, titre='Horodatage')
        self.assertIsNotNone(annonce.created_at)
        self.assertIsNotNone(annonce.updated_at)
