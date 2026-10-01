"""QJR520 (Groupe QJR5) — une version REMPLACÉE ne peut plus être signée,
relancée, expirée ni listée au portail.

Scénario reproduit EN DIRECT le 30/09 : après « Réviser », POST
/proposal/<jeton v1>/accept/ anonyme rendait 200 ; v1 passait ACCEPTE et v2
(sa « sœur » pour l'effondrement) REFUSE « variante non retenue » — plus
aucune version active, aucun BC. ``accept_devis`` refuse désormais un devis
inactif (409, rien n'est écrit — règle #4) ; relances, expiration et portail
filtrent ``is_active=True``.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_version_remplacee_non_signable"
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisNudgeLog, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class VersionRemplaceeNonSignable(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR520 Co', slug='qjr520-co')
        self.user = User.objects.create_user(
            username='qjr520_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR520',
            email='qjr520@example.test', telephone='+212600005200')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR520-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0

    def _devis(self, statut=Devis.Statut.ENVOYE, **extra):
        self.n += 1
        # Références espacées de 10 : « Réviser » numérote la v2 au plus haut
        # numéro utilisé + 1 (core.numbering) ; des références manuelles
        # consécutives entreraient en collision avec elle.
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-52{self.n}0',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            created_by=self.user, **extra)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis

    def _reviser(self, v1):
        r = self.api.post(f'/api/django/ventes/devis/{v1.id}/reviser/')
        self.assertEqual(r.status_code, 201, r.content)
        v1.refresh_from_db()
        return Devis.objects.get(pk=r.data['id'])

    def test_scenario_du_direct_signature_publique_v1_refusee(self):
        v1 = self._devis()
        lien = ShareLink.for_devis(v1)
        v2 = self._reviser(v1)
        anonyme = APIClient()
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            r = anonyme.post(
                f'/api/django/public/proposal/{lien.token}/accept/',
                {'nom': 'Client QJR520', 'consent_esign': True},
                format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn(v2.reference, r.data['detail'])
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v1.statut, Devis.Statut.ENVOYE)
        self.assertFalse(v1.is_active)
        self.assertEqual(v2.statut, Devis.Statut.BROUILLON)
        self.assertTrue(v2.is_active)

    def test_accept_devis_direct_refuse_aussi(self):
        """Portail client et action interne passent par accept_devis."""
        from apps.ventes.services import AcceptError, accept_devis
        v1 = self._devis()
        v2 = self._reviser(v1)
        with self.assertRaises(AcceptError) as leve:
            accept_devis(devis=v1, user=self.user, nom='Interne')
        self.assertTrue(leve.exception.conflict)
        self.assertIn(v2.reference, leve.exception.message)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v1.statut, Devis.Statut.ENVOYE)
        self.assertEqual(v2.statut, Devis.Statut.BROUILLON)
        self.assertTrue(v2.is_active)

    def test_version_remplacee_ni_relancee(self):
        from apps.ventes.services import send_devis_followup_nudges
        il_y_a = timezone.now() - timedelta(days=60)
        v1 = self._devis(date_envoi=il_y_a)
        self._reviser(v1)
        temoin = self._devis(date_envoi=il_y_a)
        send_devis_followup_nudges()
        self.assertFalse(DevisNudgeLog.objects.filter(devis=v1).exists())
        self.assertTrue(DevisNudgeLog.objects.filter(devis=temoin).exists())

    def test_version_remplacee_n_expire_pas(self):
        from apps.ventes.services import expire_stale_devis
        passe = timezone.now().date() - timedelta(days=30)
        v1 = self._devis(date_validite=passe)
        self._reviser(v1)
        temoin = self._devis(date_validite=passe)
        expire_stale_devis()
        v1.refresh_from_db()
        temoin.refresh_from_db()
        self.assertEqual(v1.statut, Devis.Statut.ENVOYE)
        self.assertEqual(temoin.statut, Devis.Statut.EXPIRE)

    def test_portail_ne_liste_que_la_version_en_vigueur(self):
        from apps.ventes.selectors import devis_du_client_portail
        v1 = self._devis()
        v2 = self._reviser(v1)
        v2.statut = Devis.Statut.ENVOYE
        v2.save(update_fields=['statut'])
        ids = [d['id'] for d in devis_du_client_portail(
            self.company, self.client_obj.id)]
        self.assertEqual(ids, [v2.id])
