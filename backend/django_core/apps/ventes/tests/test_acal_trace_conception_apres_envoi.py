"""ACAL41 (C-ACAL-090, D-ACAL-21) — une correction d'un devis ENVOYÉ qui ne
change QUE la conception imprimée (panneaux déplacés, ombrage retouché) est
une correction après envoi TRACÉE : « Corrigé après envoi — calepinage
(conception) », marqueur ``etude_params.resync_apres_envoi``, statut
« envoyé » inchangé (règle #4). Renvoyer le même document ne laisse aucune
trace.

Vraies Devis/LigneDevis, HTTP réel (sync-layout et layout POST).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_trace_conception_apres_envoi"
"""
import copy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, DevisActivity, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _layout(decalage=0.0, **extra):
    """10 panneaux posés sur un pan ; ``decalage`` déplace chaque panneau
    (même compte, mêmes lignes, empreinte imprimée différente)."""
    panneaux = [{'cx': 1.0 + i + decalage, 'cy': 2.0, 'face': 0}
                for i in range(10)]
    corps = {
        'scenario': 'reseau',
        'panelWatt': 710,
        'zones': [{'id': 'z1', 'label': 'Pan sud',
                   'geometry': {'count': 10, 'kwc': 7.1,
                                'azimuthDeg': 180, 'tiltDeg': 30,
                                'panels': panneaux}}],
        'result': {'panels': 10, 'kwc': 7.1,
                   'annualKwh': 12000, 'savings': 10000},
    }
    corps.update(extra)
    return corps


class TraceConceptionApresEnvoi(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACAL41 Co', slug='acal41-co')
        self.user = User.objects.create_user(
            username='acal41_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ACAL41',
            email='acal41@example.test', telephone='+212600004141')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ACAL41-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.layout = _layout()
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-4141',
            client=self.client_obj, statut='envoye',
            taux_tva=Decimal('20'), created_by=self.user,
            roof_layout=self.layout, layout_hash=layout_hash(self.layout))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'))

    def _corrections(self):
        return DevisActivity.objects.filter(
            devis=self.devis, field='correction_apres_envoi')

    def _sync(self, layout):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/sync-layout/',
            layout, format='json')

    def _assert_trace_conception(self):
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')
        corrections = self._corrections()
        self.assertEqual(corrections.count(), 1)
        corps = corrections.get().body
        self.assertIn('calepinage', corps)
        self.assertIn('conception', corps)
        self.assertIn('date', (self.devis.etude_params or {})
                      .get('resync_apres_envoi') or {})

    def test_panneaux_deplaces_sur_envoye_trace(self):
        deplace = _layout(decalage=0.5)
        self.assertNotEqual(layout_hash(deplace), self.devis.layout_hash)
        r = self._sync(deplace)
        self.assertEqual(r.status_code, 200, r.content)
        # Les lignes sont identiques : seule la conception a bougé.
        self.assertEqual(
            int(self.devis.lignes.get(produit=self.produit).quantite), 10)
        self._assert_trace_conception()

    def test_post_layout_envoye_trace(self):
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/layout/',
            _layout(decalage=0.5), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._assert_trace_conception()

    def test_retouche_ombrage_sur_envoye_trace(self):
        ombre = copy.deepcopy(self.layout)
        ombre['shading12x24'] = [[0.1] * 24 for _ in range(12)]
        r = self._sync(ombre)
        self.assertEqual(r.status_code, 200, r.content)
        self._assert_trace_conception()

    def test_renvoi_identique_sans_trace(self):
        r = self._sync(copy.deepcopy(self.layout))
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/layout/',
            copy.deepcopy(self.layout), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._corrections().count(), 0)
        self.devis.refresh_from_db()
        self.assertNotIn('resync_apres_envoi', self.devis.etude_params or {})
        self.assertEqual(self.devis.statut, 'envoye')
