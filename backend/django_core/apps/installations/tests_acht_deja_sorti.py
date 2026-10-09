"""ACHT1 (C-ACHT-001, D-ACHT-1) — « une vente = une sortie » : le « déjà
sorti » d'un chantier (vente soldée + consommation terrain F11 validée) est lu
à UNE source (`quantite_deja_sortie_chantier`) par tout écrivain de
réservation ; une V2, une réactivation ou `reserver-stock` ne re-réservent que
l'écart.

Rejoue CCRE-1 (F11 10/1 puis V2 prix seul / annuler-réactiver /
reserver-stock puis « Installé » : 20/2 sortis au lieu de 10/1) et CCRE-6
(solde vente total de 10 puis V2 à 14 : 0 sorti à « Installé » au lieu de 4).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_deja_sorti"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations import field_capture
from apps.installations.models import (
    Installation, InstallationActivity, Intervention, StockReservation,
)
from apps.installations.services import (
    _apply_stock_statut_effects, solder_reservations_vente,
)
from apps.stock.models import MouvementStock, Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()


class DejaSortiTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht1', defaults={'nom': 'Co ACHT1'})
        self.user = User.objects.create_user(
            username='resp-acht1', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT1', sku='PAN-ACHT1',
            prix_vente=Decimal('100'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT1', sku='OND-ACHT1',
            prix_vente=Decimal('1000'), quantite_stock=10)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht1@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ACHT1-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=self.v1, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        LigneDevis.objects.create(
            devis=self.v1, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        devis_accepted.send(sender=None, devis=self.v1, user=self.user,
                            ancien_statut='envoye')
        self.inst = Installation.objects.get(devis=self.v1)
        Installation.objects.filter(pk=self.inst.pk).update(
            statut=Installation.Statut.EN_COURS)
        self.inst.refresh_from_db()

    # ── helpers ──────────────────────────────────────────────────────────
    def _url(self, action):
        return f'/api/django/installations/chantiers/{self.inst.id}/{action}/'

    def _f11_tout_pose(self):
        """F11 : la pose de 10 panneaux + 1 onduleur est validée."""
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user)
        cons = field_capture.ensure_consommation(interv)
        r = self.api.post(
            f'/api/django/installations/interventions/{interv.id}/'
            'valider-consommation/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return cons

    def _v2(self, quantite_panneaux=10, prix=Decimal('100')):
        v2 = reviser_devis(self.v1, user=self.user)
        LigneDevis.objects.filter(devis=v2, produit=self.panneau).update(
            quantite=Decimal(str(quantite_panneaux)), prix_unitaire=prix)
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        v2 = Devis.objects.get(pk=v2.pk)
        devis_accepted.send(sender=None, devis=v2, user=self.user,
                            ancien_statut='envoye')
        self.inst.refresh_from_db()
        return v2

    def _installe(self):
        self.inst.refresh_from_db()
        ancien = Installation.canonical_statut(self.inst.statut)
        Installation.objects.filter(pk=self.inst.pk).update(
            statut=Installation.Statut.INSTALLE)
        self.inst.refresh_from_db()
        _apply_stock_statut_effects(
            self.inst, ancien, Installation.Statut.INSTALLE, self.user)

    def _sortie(self, produit):
        return (MouvementStock.objects
                .filter(produit=produit, reference=self.inst.reference,
                        type_mouvement=MouvementStock.TypeMouvement.SORTIE)
                .aggregate(t=Sum('quantite'))['t']) or 0

    def _assert_sorties(self, panneaux, onduleurs):
        self.assertEqual(self._sortie(self.panneau), panneaux)
        self.assertEqual(self._sortie(self.onduleur), onduleurs)

    def _assert_second_installe_muet(self):
        avant = (self._sortie(self.panneau), self._sortie(self.onduleur))
        self._installe()
        self.assertEqual(
            (self._sortie(self.panneau), self._sortie(self.onduleur)), avant)

    # ── tests ────────────────────────────────────────────────────────────
    def test_sans_geste(self):
        """Témoin : F11 puis « Installé » = 10 / 1."""
        self._f11_tout_pose()
        self._installe()
        self._assert_sorties(10, 1)

    def test_f11_solde_la_reservation(self):
        self._f11_tout_pose()
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)
        self.assertTrue(resa.consomme)
        self.assertEqual(resa.quantite, 0)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst,
            body__contains='soldée par la consommation terrain').exists())

    def test_v2_prix_seul_apres_f11(self):
        self._f11_tout_pose()
        self._v2(prix=Decimal('90'))
        self._installe()
        self._assert_sorties(10, 1)
        self._assert_second_installe_muet()

    def test_annuler_reactiver_apres_f11(self):
        self._f11_tout_pose()
        r = self.api.post(self._url('annuler'), {'motif': 'test'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(self._url('reactiver'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._installe()
        self._assert_sorties(10, 1)

    def test_reserver_stock_apres_f11(self):
        self._f11_tout_pose()
        r = self.api.post(self._url('reserver-stock'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._installe()
        self._assert_sorties(10, 1)

    def test_solde_vente_total_puis_v2(self):
        solder_reservations_vente(
            self.inst, {self.panneau.id: 10}, 'FAC-ACHT1-1', user=self.user)
        self._v2(quantite_panneaux=14)
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)
        self.assertFalse(resa.consomme)
        self.assertTrue(resa.active)
        self.assertEqual(resa.quantite, 4)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__contains='rouverte').exists())
        self._installe()
        # 10 sortis par la vente (hors chantier) + 4 à « Installé ».
        self.assertEqual(self._sortie(self.panneau), 4)
        self._assert_second_installe_muet()
