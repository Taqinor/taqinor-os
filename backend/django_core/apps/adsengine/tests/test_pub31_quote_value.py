"""PUB31 — Valeur estimée du devis sur l'événement CAPI QUOTE_SENT (flag-gaté).

Couvre :
  - flag OFF (défaut) : QUOTE_SENT reste byte-identique (aucune clé value/
    currency), même avec un devis lié ;
  - flag ON + devis lié : ``custom_data.value``/``currency`` = TTC/devise du
    devis le plus récent du lead ;
  - flag ON mais AUCUN devis lié : jamais une valeur fabriquée (clés absentes) ;
  - flag ON mais une AUTRE étape (CONTACTED/SIGNED) : jamais enrichie (réservé
    à QUOTE_SENT) ;
  - ``signed_contract`` (capi_odoo) reste INTACT — ce module n'y touche jamais.
"""
import os
from decimal import Decimal
from unittest import mock
from uuid import uuid4

from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.crm.stages import CONTACTED, QUOTE_SENT, SIGNED
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

from apps.adsengine import capi_crm

_VALUE_ON = {'META_CRM_STAGE_CAPI_VALUE_ENABLED': '1'}


def _meta_lead(company, **kw):
    defaults = dict(
        company=company, nom='Prospect',
        source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
        external_system='meta_lead_ads', external_id='741852963',
        telephone='0612345678', stage=CONTACTED)
    defaults.update(kw)
    return Lead.objects.create(**defaults)


def _devis_with_ttc(company, lead, ttc='84000.00', devise='MAD'):
    # SKU + référence UNIQUES par appel : ce lead peut recevoir PLUSIEURS devis
    # (cf. test_uses_most_recent_devis) — sans suffixe, le 2ᵉ Produit viole
    # ``stock_produit_company_id_sku_uniq`` et le 2ᵉ Devis viole
    # ``unique_together (company, reference)``.
    suffix = uuid4().hex[:8]
    client = Client.objects.create(company=company, nom='Client PUB31')
    produit = Produit.objects.create(
        company=company, nom='Onduleur', sku=f'SKU-PUB31-{lead.id}-{suffix}',
        prix_vente=Decimal('100'), quantite_stock=10)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-PUB31-{lead.id}-{suffix}',
        client=client, lead=lead, statut=Devis.Statut.ENVOYE,
        taux_tva=Decimal('20.00'), devise=devise)
    ht = (Decimal(ttc) / Decimal('1.2')).quantize(Decimal('0.01'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Onduleur',
        quantite=Decimal('1'), prix_unitaire=ht, taux_tva=Decimal('20.00'))
    return devis


class QuoteValueFlagOffTests(TestCase):
    def test_flag_off_is_byte_identical(self):
        company = Company.objects.create(nom='PUB31 Off', slug='pub31-off')
        lead = _meta_lead(company)
        _devis_with_ttc(company, lead)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('META_CRM_STAGE_CAPI_VALUE_ENABLED', None)
            built = capi_crm.build_stage_event(
                company, lead.pk, QUOTE_SENT, old_stage=CONTACTED)
        self.assertTrue(built['eligible'])
        custom = built['event']['custom_data']
        self.assertNotIn('value', custom)
        self.assertNotIn('currency', custom)


class QuoteValueFlagOnTests(TestCase):
    def test_flag_on_adds_value_and_currency_on_quote_sent(self):
        company = Company.objects.create(nom='PUB31 On', slug='pub31-on')
        lead = _meta_lead(company)
        _devis_with_ttc(company, lead, ttc='84000.00', devise='MAD')
        with mock.patch.dict(os.environ, _VALUE_ON):
            built = capi_crm.build_stage_event(
                company, lead.pk, QUOTE_SENT, old_stage=CONTACTED)
        custom = built['event']['custom_data']
        self.assertEqual(custom['value'], 84000.00)
        self.assertEqual(custom['currency'], 'MAD')

    def test_flag_on_without_linked_devis_never_fabricates_value(self):
        company = Company.objects.create(
            nom='PUB31 No Devis', slug='pub31-no-devis')
        lead = _meta_lead(company)
        with mock.patch.dict(os.environ, _VALUE_ON):
            built = capi_crm.build_stage_event(
                company, lead.pk, QUOTE_SENT, old_stage=CONTACTED)
        custom = built['event']['custom_data']
        self.assertNotIn('value', custom)
        self.assertNotIn('currency', custom)

    def test_flag_on_but_other_stage_never_enriched(self):
        company = Company.objects.create(
            nom='PUB31 Other Stage', slug='pub31-other-stage')
        lead = _meta_lead(company, stage=QUOTE_SENT)
        _devis_with_ttc(company, lead)
        with mock.patch.dict(os.environ, _VALUE_ON):
            built = capi_crm.build_stage_event(
                company, lead.pk, SIGNED, old_stage=QUOTE_SENT)
        custom = built['event']['custom_data']
        self.assertNotIn('value', custom)
        self.assertNotIn('currency', custom)

    def test_uses_most_recent_devis(self):
        company = Company.objects.create(
            nom='PUB31 Latest', slug='pub31-latest')
        lead = _meta_lead(company)
        _devis_with_ttc(company, lead, ttc='10000.00')
        latest = _devis_with_ttc(company, lead, ttc='96000.00')
        # Deux devis du même lead — le plus RÉCENT (id le plus haut) gagne.
        self.assertGreater(latest.pk, Devis.objects.filter(
            lead=lead).exclude(pk=latest.pk).first().pk)
        with mock.patch.dict(os.environ, _VALUE_ON):
            built = capi_crm.build_stage_event(
                company, lead.pk, QUOTE_SENT, old_stage=CONTACTED)
        self.assertEqual(built['event']['custom_data']['value'], 96000.00)


class SignedContractUnchangedTests(TestCase):
    """capi_odoo.signed_contract reste INTACT — ce module ne le touche jamais."""

    def test_capi_odoo_module_never_references_pub31_flag(self):
        import inspect

        from apps.adsengine import capi_odoo
        src = inspect.getsource(capi_odoo)
        self.assertNotIn('META_CRM_STAGE_CAPI_VALUE_ENABLED', src)
