"""APRF19 — ``LeadViewSet.roi_sources`` en agrégats : +10 campagnes et +10
leads signés n'ajoutent AUCUNE requête, et le JSON reste celui d'ACRM10 +
ACRM31 (perdu/archivé non signés, V1 remplacée non comptée).

Test-du-test : remettre la boucle canal × campagne (ou ``lead.devis.filter``
par lead) ⇒ le nombre de requêtes croît et test_requetes_plates échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
URL = '/api/django/crm/leads/roi-sources/'


class RoiSourcesAgregatTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF19 Solaire', slug='aprf19-roi')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf19-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='19')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0
        self._lead_signe('meta_ads', 'base', Decimal('1000'))

    def _lead_signe(self, canal, campagne, prix, **kw):
        self.n += 1
        lead = Lead.objects.create(
            company=self.company, nom=f'L{self.n}', canal=canal,
            utm_campaign=campagne, stage=stages.SIGNED, **kw)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF19-{self.n:04d}',
            client=self.client_c, lead=lead, statut='accepte',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'APRF19-{self.n}',
            prix_vente=prix, quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=prix, remise=Decimal('0'))
        return lead, devis

    def _get(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def _nb_requetes(self):
        with CaptureQueriesContext(connection) as ctx:
            self._get()
        return len(ctx.captured_queries)

    def test_requetes_plates(self):
        self._get()  # échauffement (caches de rôles/permissions)
        avant = self._nb_requetes()
        for i in range(10):
            canal = 'meta_ads' if i % 2 else 'site_web'
            self._lead_signe(canal, f'camp-{i}', Decimal('500'))
        self.assertEqual(self._nb_requetes(), avant)

    def test_json_acrm10_acrm31(self):
        self._lead_signe('site_web', 'mix', Decimal('1000'))
        self._lead_signe('site_web', 'mix', Decimal('2000'), perdu=True,
                         motif_perte='Prix')
        self._lead_signe('site_web', 'mix', Decimal('3000'), is_archived=True)
        _, v1 = self._lead_signe('site_web', 'mix', Decimal('4000'))
        Devis.objects.filter(pk=v1.pk).update(is_active=False)
        Lead.objects.create(company=self.company, nom='Ouvert',
                            canal='site_web', utm_campaign='mix',
                            stage=stages.CONTACTED)
        ligne = next(r for r in self._get()
                     if r['canal'] == 'site_web' and r['utm_campaign'] == 'mix')
        # archivé hors périmètre ; perdu compté comme lead, pas comme signé.
        self.assertEqual(ligne['lead_count'], 4)
        self.assertEqual(ligne['signed_count'], 2)
        # 1000 HT → 1200 TTC ; la V1 inactive (4000) ne compte pas.
        # Montants multiples de 100 TTC : le palier ARRONDI-100
        # (argent.PAS_ARRONDI_DEVIS) ne les touche pas.
        self.assertEqual(ligne['signed_value_ttc'], 1200.0)
        self.assertEqual(ligne['win_rate'], 50.0)
