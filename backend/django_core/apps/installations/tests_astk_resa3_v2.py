"""ASTK177 — une V2 acceptée RÉALIGNE la nomenclature et les réservations du
chantier (décision fondateur ASTK173 du 07/10/2026 : (a) « réaligner »).

Rejoue la reproduction RESA-3 : v1 accepté (panneaux 10 + onduleur 1 →
réservations 10 / 1) → v2 révisée à 14 panneaux + 1 batterie (onduleur
retiré) puis acceptée. ROUGE AVANT : `_rattacher_chantier_de_revision`
rattachait le chantier à la V2 mais gardait `Installation.bom` = V1 et les
réservations V1 (panneaux 10, batterie absente, onduleur toujours réservé).

Attendu : tant que le chantier n'est pas « Installé », bom = V2, réservations
panneaux 14 / batterie 1, aucune réservation active d'un SKU absent de la V2 ;
une quantité déjà sortie (soldée par la vente) n'est jamais re-réservée ; un
chantier « Installé » n'est jamais réaligné.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_astk_resa3_v2"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, InstallationActivity, StockReservation,
)
from apps.installations.services import solder_reservations_vente
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()


class RevisionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk177', defaults={'nom': 'Co ASTK177'})
        self.user = User.objects.create_user(
            username='resp-astk177', password='x', company=self.company,
            role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK177', sku='PAN-177',
            prix_vente=Decimal('100'), quantite_stock=50)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK177', sku='OND-177',
            prix_vente=Decimal('1000'), quantite_stock=5)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie ASTK177', sku='BAT-177',
            prix_vente=Decimal('2000'), quantite_stock=5)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='astk177@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ASTK177-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=self.v1, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        LigneDevis.objects.create(
            devis=self.v1, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        self._accepter(self.v1)
        self.inst = Installation.objects.get(devis=self.v1)

    # ── helpers ──────────────────────────────────────────────────────────
    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def _v2(self):
        """V2 révisée : panneaux 14, batterie 1, onduleur retiré."""
        v2 = reviser_devis(self.v1, user=self.user)
        LigneDevis.objects.filter(devis=v2, produit=self.onduleur).delete()
        LigneDevis.objects.filter(devis=v2, produit=self.panneau).update(
            quantite=Decimal('14'))
        LigneDevis.objects.create(
            devis=v2, produit=self.batterie, designation='Batterie',
            quantite=Decimal('1'), prix_unitaire=Decimal('2000'))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        return Devis.objects.get(pk=v2.pk)

    def _actives(self):
        return dict(StockReservation.objects.filter(
            installation=self.inst, active=True).values_list(
                'produit_id', 'quantite'))

    def _bom_ids(self):
        self.inst.refresh_from_db()
        return {li['produit_id']: li['quantite'] for li in self.inst.bom}

    # ── tests ────────────────────────────────────────────────────────────
    def test_preconditions_v1(self):
        self.assertEqual(self._actives(),
                         {self.panneau.id: 10, self.onduleur.id: 1})

    def test_v2_acceptee_realigne_les_reservations(self):
        v2 = self._v2()
        self._accepter(v2)

        self.assertEqual(
            Installation.objects.filter(company=self.company).count(), 1)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.devis_id, v2.pk)
        self.assertEqual(self._bom_ids(),
                         {self.panneau.id: 14.0, self.batterie.id: 1.0})
        self.assertEqual(self._actives(),
                         {self.panneau.id: 14, self.batterie.id: 1})
        # Le SKU disparu (onduleur) est libéré, jamais supprimé.
        resa_ond = StockReservation.objects.get(
            installation=self.inst, produit=self.onduleur)
        self.assertFalse(resa_ond.active)
        self.assertFalse(resa_ond.consomme)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__contains=v2.reference).exists())

    def test_quantite_deja_sortie_jamais_rereservee(self):
        # La vente a déjà sorti 4 panneaux : réservation soldée 10 → 6.
        solder_reservations_vente(
            self.inst, {self.panneau.id: 4}, 'FAC-ASTK177-1', user=self.user)
        self.assertEqual(self._actives()[self.panneau.id], 6)

        self._accepter(self._v2())

        # V2 = 14 dont 4 déjà sortis → reste à réserver 10, jamais 14.
        self.assertEqual(self._actives()[self.panneau.id], 10)

    def test_reservation_consommee_reste_figee(self):
        StockReservation.objects.filter(
            installation=self.inst, produit=self.onduleur).update(
                consomme=True)
        self._accepter(self._v2())
        resa_ond = StockReservation.objects.get(
            installation=self.inst, produit=self.onduleur)
        self.assertTrue(resa_ond.consomme)
        self.assertTrue(resa_ond.active)
        self.assertEqual(resa_ond.quantite, 1)

    def test_chantier_installe_aucun_realignement(self):
        Installation.objects.filter(pk=self.inst.pk).update(
            statut=Installation.Statut.INSTALLE)
        bom_avant = self._bom_ids()
        actives_avant = self._actives()

        v2 = self._v2()
        self._accepter(v2)

        self.inst.refresh_from_db()
        self.assertEqual(self.inst.devis_id, v2.pk)  # rattaché quand même
        self.assertEqual(self._bom_ids(), bom_avant)
        self.assertEqual(self._actives(), actives_avant)
