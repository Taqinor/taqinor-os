"""AANA76 — l'attribution du CA signé (``attribution_leads``,
``revenu_attribue_campagne``) suit la règle des ventes EN VIGUEUR de
``devis_signes_en_vigueur`` (VNT22) : une V1 acceptée révisée en V2 brouillon
porte son CA, et les requêtes ne dépendent pas du nombre de leads.

Test-du-test : ne plus passer ``en_vigueur`` au prédicat ⇒ le repli exact
coûte une requête par devis et ``test_requetes_constantes`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors import devis_signes_en_vigueur

User = get_user_model()
CAMPAGNE = 'aana76-camp'


class AttributionVentesEnVigueurTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='AANA76', slug='aana76')
        self.u1 = User.objects.create_user(
            username='aana76-a', password='x', company=self.company,
            role_legacy='responsable')
        self.u2 = User.objects.create_user(
            username='aana76-b', password='x', company=self.company,
            role_legacy='responsable')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='76')
        self.today = aujourd_hui_local()
        self.n = 0

    def _lead_signe(self, owner, canal, prix=Decimal('1000')):
        self.n += 1
        lead = Lead.objects.create(
            company=self.company, nom=f'L{self.n}', owner=owner,
            client=self.client_c, stage=stages.SIGNED, canal=canal,
            utm_campaign=CAMPAGNE)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AANA76-{self.n:04d}',
            client=self.client_c, lead=lead, statut='accepte',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=owner, date_acceptation=self.today)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'AANA76-{self.n}',
            prix_vente=prix, quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=prix, remise=Decimal('0'))
        return lead, devis

    def _attendu(self):
        ids = list(Lead.objects.filter(company=self.company)
                   .values_list('pk', flat=True))
        return sum((Decimal(str(d.total_ttc)) for d in
                    devis_signes_en_vigueur(self.company, lead_ids=ids)),
                   Decimal('0'))

    def test_v1_en_vigueur_porte_le_ca(self):
        # lead 1 : V1 acceptée révisée en V2 BROUILLON (V1 reste la vente)
        _, v1 = self._lead_signe(self.u1, 'meta_ads')
        reviser_devis(Devis.objects.get(pk=v1.pk), user=self.u1)
        # lead 2 : V1 puis V2 acceptées (V2 seule)
        _, v1b = self._lead_signe(self.u2, 'site_web')
        v2b = reviser_devis(Devis.objects.get(pk=v1b.pk), user=self.u2)
        Devis.objects.filter(pk=v2b.pk).update(
            statut='accepte', date_acceptation=self.today)
        # lead 3 : jamais révisé
        self._lead_signe(self.u2, 'site_web')
        attendu = self._attendu().quantize(Decimal('0.01'))
        attribution = selectors.attribution_leads(self.company)
        par_com = {c['commercial']: c for c in attribution['par_commercial']}
        total_com = sum(Decimal(c['ca_signe']) for c in par_com.values())
        total_src = sum(Decimal(s['ca_signe'])
                        for s in attribution['par_source'])
        self.assertEqual(total_com.quantize(Decimal('0.01')), attendu)
        self.assertEqual(total_src.quantize(Decimal('0.01')), attendu)
        self.assertGreater(Decimal(par_com['aana76-a']['ca_signe']), 0)
        self.assertEqual(par_com['aana76-a']['nb_signes'], 1)
        revenu = selectors.revenu_attribue_campagne(self.company, CAMPAGNE)
        self.assertEqual(
            Decimal(revenu['revenu_ttc']).quantize(Decimal('0.01')), attendu)
        self.assertEqual(revenu['nb_signes'], 3)

    def _nb_requetes(self):
        with CaptureQueriesContext(connection) as ctx:
            selectors.attribution_leads(self.company)
            selectors.revenu_attribue_campagne(self.company, CAMPAGNE)
        return len(ctx.captured_queries)

    def test_requetes_constantes(self):
        for _ in range(3):
            self._lead_signe(self.u1, 'meta_ads')
        avant = self._nb_requetes()
        for _ in range(27):
            self._lead_signe(self.u2, 'site_web')
        self.assertEqual(self._nb_requetes(), avant)
