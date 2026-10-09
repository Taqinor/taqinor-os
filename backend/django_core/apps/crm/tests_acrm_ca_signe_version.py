"""ACRM10 (C-ACRM-006) — le CA « signé » des lecteurs crm ne compte que la
version EN VIGUEUR d'une révision acceptée (``statut='accepte'`` ET
``is_active=True``), comme ``reporting.pipeline._devis_signes``.

Sonde V_VA LSEL-1 : un devis accepté de 53 500 TTC révisé en V2 de 72 500
acceptée comptait 126 000 dans les lecteurs crm, 72 500 dans le reporting.
Révision RÉELLE par ``ventes.domain.revision.reviser_devis`` (jamais un
clone fait main). Aucun statut de devis n'est écrit par le code testé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.dates import aujourd_hui_local

from apps.crm import selectors, stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
CAMPAGNE = 'acrm10-campagne'


class CaSigneVersionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM10 Solaire', slug='acrm10-version')
        self.user = User.objects.create_user(
            username='acrm10-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='Signe')
        self.lead = Lead.objects.create(
            company=self.company, nom='Signe', owner=self.user,
            client=self.client_c, stage=stages.SIGNED,
            utm_campaign=CAMPAGNE, canal='meta_ads')
        self.today = aujourd_hui_local()
        self.v1 = self._devis_accepte('DEV-ACRM10-0001', Decimal('1000'))
        v2 = reviser_devis(self.v1, user=self.user)
        LigneDevis.objects.filter(devis=v2).update(
            prix_unitaire=Decimal('2500'))
        Devis.objects.filter(pk=v2.pk).update(
            statut='accepte', date_acceptation=self.today)
        self.v1.refresh_from_db()
        self.v2 = Devis.objects.get(pk=v2.pk)
        self.assertFalse(self.v1.is_active)
        self.assertEqual(self.v1.statut, 'accepte')
        self.attendu = Decimal(str(self.v2.total_ttc))
        self.somme_deux = self.attendu + Decimal(str(self.v1.total_ttc))

    def _devis_accepte(self, reference, prix):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_c,
            lead=self.lead, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            date_acceptation=self.today)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            sku=f'{reference}-P', prix_vente=prix, quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 550W',
            quantite=Decimal('10'), prix_unitaire=prix, remise=Decimal('0'))
        return devis

    def _lecteurs(self):
        attribution = selectors.attribution_leads(self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        resp = api.get('/api/django/crm/leads/roi-sources/')
        self.assertEqual(resp.status_code, 200, resp.content)
        roi = next(g for g in resp.data if g.get('utm_campaign') == CAMPAGNE)
        return {
            'roi_sources': Decimal(str(roi['signed_value_ttc'])),
            '_ca_signe_mois': selectors._ca_signe_mois(
                self.company, [self.user.pk], today=self.today),
            'attribution_leads': Decimal(
                attribution['par_commercial'][0]['ca_signe']),
            'revenu_attribue_campagne': Decimal(
                selectors.revenu_attribue_campagne(
                    self.company, CAMPAGNE)['revenu_ttc']),
        }

    def test_revision_compte_v2_seule(self):
        for lecteur, valeur in self._lecteurs().items():
            self.assertEqual(valeur.quantize(Decimal('0.01')),
                             self.attendu.quantize(Decimal('0.01')), lecteur)
            self.assertNotEqual(valeur.quantize(Decimal('0.01')),
                                self.somme_deux.quantize(Decimal('0.01')),
                                lecteur)

    def test_parite_reporting(self):
        from apps.reporting.pipeline import _devis_signes
        reporting = sum((Decimal(str(d.total_ttc)) for d in _devis_signes(
            {'company': self.company})), Decimal('0'))
        self.assertEqual(reporting.quantize(Decimal('0.01')),
                         self.attendu.quantize(Decimal('0.01')))
        self.assertEqual(
            selectors._ca_signe_mois(
                self.company, [self.user.pk], today=self.today
            ).quantize(Decimal('0.01')),
            reporting.quantize(Decimal('0.01')))

    def test_devis_accepte_unique_inchange(self):
        autre = Company.objects.create(nom='ACRM10 B', slug='acrm10-b')
        user = User.objects.create_user(
            username='acrm10-b', password='x', company=autre,
            role_legacy='responsable')
        client = Client.objects.create(company=autre, nom='B')
        lead = Lead.objects.create(company=autre, nom='B', owner=user,
                                   client=client, stage=stages.SIGNED)
        devis = Devis.objects.create(
            company=autre, reference='DEV-ACRM10-B', client=client, lead=lead,
            statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=user,
            date_acceptation=self.today)
        produit = Produit.objects.create(
            company=autre, nom='Onduleur', sku='ACRM10-B-O',
            prix_vente=Decimal('5000'), quantite_stock=3)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Onduleur réseau',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            remise=Decimal('0'))
        self.assertEqual(
            selectors._ca_signe_mois(autre, [user.pk], today=self.today),
            Decimal(str(devis.total_ttc)))
