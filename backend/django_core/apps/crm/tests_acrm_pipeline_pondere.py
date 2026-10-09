"""ACRM34 — La carte « Mes équipes » (``stats_equipe``) calcule son pipeline
pondéré comme le forecast (XSAL7) : ``_lead_forecast_value`` ×
``_lead_win_weight`` — rejoue la sonde LSEL-9.

Test-du-test : remettre ``_lead_value`` ⇒ test_parite_forecast et
test_montant_estime_pre_devis_pese échouent.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm import selectors, stages
from apps.crm.models import Client, EquipeCommerciale, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


class PipelinePondereTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM34 Solaire', slug='acrm34-pondere')
        self.com = User.objects.create_user(
            username='acrm34-com', password='x', company=self.company,
            role_legacy='commercial')
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe 34', responsable=self.com)
        self.equipe.membres.set([self.com])
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='34')

    def _lead(self, **kw):
        return Lead.objects.create(
            company=self.company, nom='Lead', owner=self.com,
            stage=stages.CONTACTED, **kw)

    def _devis(self, lead, statut, prix=Decimal('1000')):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ACRM34-{lead.pk}',
            client=self.client_c, lead=lead, statut=statut,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.com)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'ACRM34-{lead.pk}',
            prix_vente=prix, quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=prix, remise=Decimal('0'))
        return devis

    def _pondere(self):
        carte = next(e for e in selectors.stats_equipe(self.company)
                     if e['id'] == self.equipe.id)
        return Decimal(carte['pipeline_pondere'])

    def test_devis_refuse_ne_pese_pas(self):
        lead = self._lead()
        self._devis(lead, 'refuse')
        self.assertEqual(self._pondere(), Decimal('0'))

    def test_montant_estime_pre_devis_pese(self):
        self._lead(montant_estime=Decimal('50000'))
        self.assertGreater(self._pondere(), Decimal('0'))

    def test_parite_forecast(self):
        from apps.reporting.pipeline import (
            _lead_forecast_value, _lead_win_weight)
        self._lead(montant_estime=Decimal('50000'))
        refuse = self._lead(montant_estime=Decimal('20000'))
        self._devis(refuse, 'refuse')
        actif = self._lead()
        self._devis(actif, 'envoye')
        leads = Lead.objects.filter(company=self.company)
        attendu = sum(
            (_lead_forecast_value(le) * _lead_win_weight(le) for le in leads),
            Decimal('0'))
        self.assertGreater(attendu, Decimal('0'))
        self.assertEqual(self._pondere().quantize(Decimal('0.01')),
                         attendu.quantize(Decimal('0.01')))
