"""ACAL100 (C-ACAL-110) — la resynchro n'estampille l'empreinte que si l'écart
de calepinage a été ENTIÈREMENT appliqué.

Une abstention (quantité TAPÉE par le vendeur, ligne commune QJR98, cible 0)
laisse ``Devis.layout_hash`` à son ancienne valeur et le DIT : le devis reste
« à resynchroniser », et le clic suivant — une fois la cause levée —
ré-applique l'écart au lieu de répondre « inchangé ».

``reconcilier`` RÉEL (via la route ``sync-layout``), aucun mock.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_resync_ecart_residuel"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, LigneDevis, DevisActivity
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _layout(panneaux):
    return {'scenario': 'reseau', 'panelWatt': 550,
            'result': {'panels': panneaux, 'kwc': round(panneaux * 0.55, 2),
                       'annualKwh': 9000, 'savings': 7000}}


class EcartResiduelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACAL100 Co',
                                              slug='acal100-co')
        self.user = User.objects.create_user(
            username='acal100', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(company=self.company,
                                       nom='Client ACAL100')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='A100-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.layout_a = _layout(10)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-1001',
            client=client, statut='brouillon', taux_tva=Decimal('20'),
            created_by=self.user, roof_layout=self.layout_a,
            layout_hash=layout_hash(self.layout_a))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau,
            designation=self.panneau.nom, quantite=Decimal('10'),
            quantite_manuelle=True, prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))

    def _sync(self, layout):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.pk}/sync-layout/', layout,
            format='json')

    def _hash_en_base(self):
        return Devis.objects.values_list(
            'layout_hash', flat=True).get(pk=self.devis.pk)

    def test_quantite_verrouillee_ne_pose_pas_empreinte(self):
        r = self._sync(_layout(12))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.data['inchange'])
        texte = ' '.join(r.data['avertissements'])
        self.assertIn('verrouillée', texte)
        self.assertIn("n'a pas été appliqué", texte)
        self.assertIn('à resynchroniser', texte)
        # L'empreinte relue en BASE est l'ancienne (A), jamais celle de B.
        self.assertEqual(self._hash_en_base(), layout_hash(self.layout_a))
        self.assertNotEqual(self._hash_en_base(), layout_hash(_layout(12)))
        self.ligne.refresh_from_db()
        self.assertEqual(int(self.ligne.quantite), 10)
        # Aucune ligne n'a changé : aucune trace « corrigé après envoi ».
        self.assertFalse(DevisActivity.objects.filter(
            devis=self.devis, field='correction_apres_envoi').exists())
        # Le même B renvoyé n'est PAS « inchangé » : l'écart reste ouvert.
        r = self._sync(_layout(12))
        self.assertFalse(r.data['inchange'])

    def test_apres_deverrouillage_resync_applique(self):
        self.assertEqual(self._sync(_layout(12)).status_code, 200)
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite_manuelle=False)
        r = self._sync(_layout(12))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.data['inchange'])
        self.ligne.refresh_from_db()
        self.assertEqual(int(self.ligne.quantite), 12)
        self.assertEqual(self._hash_en_base(), layout_hash(_layout(12)))
        # Désormais appliqué : le renvoi est « inchangé ».
        self.assertTrue(self._sync(_layout(12)).data['inchange'])

    def test_cible_zero_ne_pose_pas_empreinte(self):
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite_manuelle=False)
        vide = _layout(0)
        r = self._sync(vide)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('aucun panneau', ' '.join(r.data['avertissements']))
        self.assertEqual(self._hash_en_base(), layout_hash(self.layout_a))
        self.ligne.refresh_from_db()
        self.assertEqual(int(self.ligne.quantite), 10)
