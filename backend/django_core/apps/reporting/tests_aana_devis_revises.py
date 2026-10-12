"""AANA19 (C-AANA-019, D-AANA-5) — un devis accepté puis RÉVISÉ en V2
acceptée n'est compté qu'UNE fois comme « signé ».

Scénario R1 : V1 acceptée puis révisée (V1 reste ``accepte`` mais
``is_active=False``, ``superseded_by=V2``), V2 acceptée active. Avant le
correctif : commissions count=2 (base 20 000 pour un devis de 10 000),
``nb_acceptes=2`` au tableau de bord.

Données RÉELLES en base (aucun mock) ; tous les sites passent par le helper
unique ``apps.reporting.pipeline._devis_signes`` — retirer ``is_active=True``
du helper (ou d'un site) rougit ce test.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestDevisReviseCompteUneFois(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana19-co', defaults={'nom': 'AANA19 Co'})[0]
        self.admin = User.objects.create_user(
            username='aana19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.commercial = User.objects.create_user(
            username='aana19_comm', password='x', role_legacy='responsable',
            company=self.company)
        prof = CompanyProfile.get(self.company)
        prof.commission_mode = 'pct_devis'
        prof.commission_valeur = Decimal('5')
        prof.save(update_fields=['commission_mode', 'commission_valeur'])

        client = Client.objects.create(company=self.company, nom='Cli R1')
        lead = Lead.objects.create(
            company=self.company, nom='Lead R1', stage=stages.SIGNED,
            owner=self.commercial)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='AANA19-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-AANA19-V1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today())
        LigneDevis.objects.create(
            devis=self.v1, produit=produit, designation='P',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        self.v2 = Devis.objects.create(
            company=self.company, reference='DEV-AANA19-V2', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today(), version=2, version_parent=self.v1)
        LigneDevis.objects.create(
            devis=self.v2, produit=produit, designation='P',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        # État laissé par la révision : V1 acceptée mais remplacée (inactive).
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2)

    def test_revision_comptee_une_fois(self):
        # Commissions (mode pct_devis 5 %) : 1 devis, base = HT de V2 seul.
        resp = self.api.get(f'{BASE}/insights/commissions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['rows']), 1)
        row = resp.data['rows'][0]
        self.assertEqual(row['count'], 1)
        self.assertEqual(Decimal(row['base']), Decimal('10000'))
        self.assertEqual(Decimal(row['commission']), Decimal('500'))

        # Tableau de bord : 1 devis accepté.
        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['conversion']['nb_acceptes'], 1)

        # Classement (export) et classement du tableau commercial : 1 signé.
        resp = self.api.get(f'{BASE}/insights/sales-leaderboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['rows'][0]['nb_devis_signes'], 1)
        resp = self.api.get(f'{BASE}/commercial/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['leaderboard'][0]['nb_devis_signes'], 1)
        # Vélocité : un seul échantillon.
        self.assertEqual(resp.data['sales_velocity']['sample_count'], 1)

        # Analytics lead→signature : un seul échantillon.
        resp = self.api.get(f'{BASE}/insights/analytics/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lead_to_signature_count'], 1)

        # Seaux de statut (rapport ventes + pipeline) : 1 accepté.
        resp = self.api.get(f'{BASE}/reports/sales/')
        self.assertEqual(resp.status_code, 200)
        acc = [b for b in resp.data['devis_par_statut']
               if b['statut'] == Devis.Statut.ACCEPTE]
        self.assertEqual(acc[0]['count'], 1)
        resp = self.api.get(f'{BASE}/pipeline/')
        self.assertEqual(resp.status_code, 200)
        acc = [b for b in resp.data['devis_par_statut']
               if b['statut'] == Devis.Statut.ACCEPTE]
        self.assertEqual(acc[0]['count'], 1)


class TestDevisSignesEnVigueurVNT22(TestCase):
    """VNT22 (couvre ADEV46) — ``devis_signes_en_vigueur`` : le dernier
    ACCEPTÉ de chaque chaîne de RÉVISION ; la V1 reste la vente tant que sa
    révision n'est pas acceptée. ``_devis_signes`` et
    ``devis_acceptes_actifs`` délèguent."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead VNT22', stage=stages.SIGNED)
        self.n = 0

    def _devis(self, statut=Devis.Statut.ACCEPTE, **champs):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        self.n += 1
        return creer_devis_388(self.company, self.user, self.client_obj,
                               f'DEV-VNT22-{self.n:03d}', statut=statut,
                               lead=self.lead, **champs)

    def _reviser(self, v1, statut, **champs):
        v2 = self._devis(statut=statut, version=v1.version + 1,
                         version_parent=v1.version_parent or v1, **champs)
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        return v2

    def _en_vigueur(self):
        from apps.reporting.pipeline import _devis_signes
        from apps.ventes.selectors import (
            devis_acceptes_actifs, devis_signes_en_vigueur)
        ids = set(devis_signes_en_vigueur(
            self.company, lead_ids=[self.lead.pk]).values_list(
                'pk', flat=True))
        self.assertEqual(
            {d.pk for d in devis_acceptes_actifs(self.company,
                                                 lead_id=self.lead.pk)},
            ids)
        self.assertEqual(
            set(_devis_signes({'company': self.company})
                .filter(lead=self.lead).values_list('pk', flat=True)), ids)
        return ids

    def test_v1_reste_la_vente_pendant_la_revision(self):
        v1 = self._devis()
        self._reviser(v1, Devis.Statut.BROUILLON)
        self.assertEqual(self._en_vigueur(), {v1.pk})

    def test_v2_acceptee_seule(self):
        v1 = self._devis()
        v2 = self._reviser(v1, Devis.Statut.ACCEPTE)
        self.assertEqual(self._en_vigueur(), {v2.pk})

    def test_v2_refusee_ou_expiree_laisse_v1(self):
        for statut in (Devis.Statut.REFUSE, Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                v1 = self._devis()
                self._reviser(v1, statut)
                self.assertIn(v1.pk, self._en_vigueur())

    def test_v2_des_acceptee_aucune_version(self):
        """V2 acceptée (preuve DevisSignature) puis dés-acceptée (sortie de
        Signé : statut repassé « envoyé », signature gardée)."""
        from django.utils import timezone
        from apps.ventes.models import DevisSignature
        v1 = self._devis()
        v2 = self._reviser(v1, Devis.Statut.ENVOYE)
        DevisSignature.objects.create(
            company=self.company, devis=v2, signataire_nom='Client',
            signed_at=timezone.now())
        self.assertEqual(self._en_vigueur(), set())

    def test_chaine_kharbachi_comptee_une_fois(self):
        """367 (54 500) → 387 → 388 (49 000) acceptés : 49 000, jamais
        152 500 ; + la chaîne neuve 389 : 98 000 (avant réparation)."""
        from apps.ventes.selectors import devis_signes_en_vigueur
        v367 = self._devis(remise_globale=Decimal('0'))
        self.assertEqual(v367.total_ttc, Decimal('54500.00'))
        v387 = self._reviser(v367, Devis.Statut.ACCEPTE)
        v388 = self._reviser(v387, Devis.Statut.ACCEPTE)
        en_vigueur = devis_signes_en_vigueur(self.company,
                                             lead_ids=[self.lead.pk])
        self.assertEqual({d.pk for d in en_vigueur}, {v388.pk})
        self.assertEqual(sum(d.total_ttc for d in en_vigueur),
                         Decimal('49000.00'))
        self._devis()  # 389 : chaîne neuve acceptée par lien public
        en_vigueur = devis_signes_en_vigueur(self.company,
                                             lead_ids=[self.lead.pk])
        self.assertEqual(sum(d.total_ttc for d in en_vigueur),
                         Decimal('98000.00'))
