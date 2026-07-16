"""QX24 — l'étude (payback) ne peut plus silencieusement se périmer.

Quand une ligne est ajoutée/éditée/supprimée ou la remise globale change, le
payback dérivé (= TTC courant ÷ économies annuelles) est recalculé et
repersisté, tout en respectant un override vendeur explicite.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import refresh_etude_consistency

MONTH = timezone.now().strftime('%Y%m')


class Qx24EtudeConsistencyTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx24-co', defaults={'nom': 'QX24 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX24',
            telephone='+212600000046')

    def _devis(self, ref, eco=10000, extra_params=None):
        params = {'economies_annuelles': eco, 'production_annuelle': 15000}
        if extra_params:
            params.update(extra_params)
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            etude_params=params)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'{ref}-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('50'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis, produit

    def test_line_add_recomputes_payback(self):
        devis, produit = self._devis(f'DEV-{MONTH}-QX2401')
        # 50×1000 = 50000 HT ; TTC 60000 ; eco 10000 → payback 6.0 ans.
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('payback_annees'), 6.0)
        # Ajoute une ligne → total monte → payback recalculé (signal).
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 2',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        devis.refresh_from_db()
        # 60×1000 = 60000 HT ; TTC 72000 ; eco 10000 → payback 7.2 ans.
        self.assertEqual(devis.etude_params.get('payback_annees'), 7.2)

    def test_line_delete_recomputes_payback(self):
        devis, produit = self._devis(f'DEV-{MONTH}-QX2402')
        extra = LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Extra',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('payback_annees'), 7.2)
        extra.delete()
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('payback_annees'), 6.0)

    def test_remise_change_recomputes_payback(self):
        devis, _ = self._devis(f'DEV-{MONTH}-QX2403')
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('payback_annees'), 6.0)
        devis.remise_globale = Decimal('20')
        devis.save(update_fields=['remise_globale'])
        devis.refresh_from_db()
        # 50000 HT − 20 % = 40000 ; TTC 48000 ; eco 10000 → payback 4.8 ans.
        self.assertEqual(devis.etude_params.get('payback_annees'), 4.8)

    def test_seller_override_preserved(self):
        devis, produit = self._devis(
            f'DEV-{MONTH}-QX2404',
            extra_params={'etude_overrides': ['payback_annees'],
                          'payback_annees': 3.0})
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Extra',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        devis.refresh_from_db()
        # Override vendeur respecté : payback inchangé.
        self.assertEqual(devis.etude_params.get('payback_annees'), 3.0)

    def test_no_economies_is_noop(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX2405',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), etude_params={})
        refresh_etude_consistency(devis)
        devis.refresh_from_db()
        self.assertNotIn('payback_annees', devis.etude_params or {})
